"""Authentication service with password and SSH key support."""

import base64
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    AuthMethod,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    parse_ssh_public_key,
    verify_password,
    verify_ssh_signature,
)
from app.models.user import User
from app.schemas.user import Token, UserCreate


class AuthService:
    """Service for handling authentication."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection for SSH challenge storage."""
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url)
        return self._redis

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user with password authentication."""
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            preferred_auth_method=AuthMethod.PASSWORD,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_user_by_username(self, username: str) -> User | None:
        """Get a user by username."""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get a user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def authenticate_password(self, username: str, password: str) -> User | None:
        """Authenticate a user with username and password."""
        user = await self.get_user_by_username(username)
        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        return user

    async def generate_ssh_challenge(self, username: str) -> tuple[str, datetime] | None:
        """Generate an SSH authentication challenge for a user."""
        user = await self.get_user_by_username(username)
        if not user or not user.ssh_public_key:
            return None

        challenge = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=5)

        # Store challenge in Redis with expiration
        redis_client = await self._get_redis()
        challenge_key = f"ssh_challenge:{username}"
        await redis_client.setex(
            challenge_key,
            timedelta(minutes=5),
            challenge,
        )

        return challenge, expires_at

    async def authenticate_ssh(
        self,
        username: str,
        challenge: str,
        signature_b64: str,
    ) -> User | None:
        """Authenticate a user with SSH key signature."""
        user = await self.get_user_by_username(username)
        if not user or not user.ssh_public_key:
            return None

        if not user.is_active:
            return None

        # Verify challenge from Redis
        redis_client = await self._get_redis()
        challenge_key = f"ssh_challenge:{username}"
        stored_challenge = await redis_client.get(challenge_key)

        if not stored_challenge or stored_challenge.decode() != challenge:
            return None

        # Delete the challenge after use
        await redis_client.delete(challenge_key)

        # Parse public key and verify signature
        public_key = parse_ssh_public_key(user.ssh_public_key)
        if not public_key:
            return None

        try:
            signature = base64.b64decode(signature_b64)
        except Exception:
            return None

        if not verify_ssh_signature(public_key, signature, challenge.encode()):
            return None

        return user

    async def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for a user."""
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={"username": user.username},
        )
        refresh_token = create_refresh_token(subject=str(user.id))

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_access_token(self, refresh_token: str) -> Token | None:
        """Refresh an access token using a refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = await self.get_user_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            return None

        return await self.create_tokens(user)

    async def update_ssh_key(self, user: User, ssh_public_key: str) -> bool:
        """Update a user's SSH public key."""
        # Validate the key format
        if not parse_ssh_public_key(ssh_public_key):
            return False

        user.ssh_public_key = ssh_public_key
        await self.db.commit()
        return True

    async def update_password(self, user: User, new_password: str) -> None:
        """Update a user's password."""
        user.password_hash = get_password_hash(new_password)
        await self.db.commit()

    async def switch_auth_method(self, user: User, method: AuthMethod) -> bool:
        """Switch a user's preferred authentication method."""
        if method == AuthMethod.PASSWORD and not user.has_password_auth:
            return False
        if method == AuthMethod.SSH_KEY and not user.has_ssh_auth:
            return False

        user.preferred_auth_method = method
        await self.db.commit()
        return True

    async def get_current_user(self, token: str) -> User | None:
        """Get the current user from a JWT token."""
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return await self.get_user_by_id(uuid.UUID(user_id))
