"""Security utilities for authentication and authorization."""

import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.asymmetric.types import PublicKeyTypes
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthMethod(StrEnum):
    """Supported authentication methods."""

    PASSWORD = "password"
    SSH_KEY = "ssh_key"


class TokenType(StrEnum):
    """JWT token types."""

    ACCESS = "access"
    REFRESH = "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": TokenType.ACCESS,
        "iat": datetime.now(UTC),
    }
    if additional_claims:
        to_encode.update(additional_claims)

    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": TokenType.REFRESH,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def generate_ssh_challenge() -> str:
    """Generate a random challenge for SSH authentication."""
    return secrets.token_urlsafe(32)


def parse_ssh_public_key(key_data: str) -> PublicKeyTypes | None:
    """Parse an OpenSSH format public key."""
    try:
        # Handle OpenSSH format (ssh-rsa, ssh-ed25519, etc.)
        key_data = key_data.strip()
        if key_data.startswith("ssh-"):
            return serialization.load_ssh_public_key(key_data.encode())
        # Handle PEM format
        return serialization.load_pem_public_key(key_data.encode())
    except Exception:
        return None


def verify_ssh_signature(
    public_key: PublicKeyTypes,
    signature: bytes,
    challenge: bytes,
) -> bool:
    """Verify an SSH signature against a challenge."""
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            public_key.verify(
                signature,
                challenge,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        elif isinstance(public_key, ed25519.Ed25519PublicKey):
            public_key.verify(signature, challenge)
            return True
        else:
            # Unsupported key type
            return False
    except Exception:
        return False
