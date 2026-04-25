"""SSO authentication service."""

import uuid
from dataclasses import dataclass
from enum import StrEnum

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import AuthMethod
from app.models.user import User


class SSOProvider(StrEnum):
    """Supported SSO providers."""

    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


@dataclass
class SSOUserInfo:
    """User info from SSO provider."""

    provider: SSOProvider
    provider_id: str
    email: str
    username: str


class SSOService:
    """Service for SSO authentication."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def get_authorization_url(self, provider: SSOProvider, redirect_uri: str) -> str | None:
        """Get the OAuth authorization URL for a provider."""
        if provider == SSOProvider.GOOGLE:
            if not settings.sso_google_client_id:
                return None
            return (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={settings.sso_google_client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"response_type=code&"
                f"scope=openid%20email%20profile&"
                f"access_type=offline"
            )
        elif provider == SSOProvider.GITHUB:
            if not settings.sso_github_client_id:
                return None
            return (
                f"https://github.com/login/oauth/authorize?"
                f"client_id={settings.sso_github_client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"scope=user:email"
            )
        elif provider == SSOProvider.MICROSOFT:
            if not settings.sso_microsoft_client_id:
                return None
            tenant = settings.sso_microsoft_tenant_id
            return (
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?"
                f"client_id={settings.sso_microsoft_client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"response_type=code&"
                f"scope=openid%20email%20profile"
            )
        return None

    async def exchange_code(self, provider: SSOProvider, code: str, redirect_uri: str) -> SSOUserInfo | None:
        """Exchange authorization code for user info."""
        if provider == SSOProvider.GOOGLE:
            return await self._exchange_google(code, redirect_uri)
        elif provider == SSOProvider.GITHUB:
            return await self._exchange_github(code, redirect_uri)
        elif provider == SSOProvider.MICROSOFT:
            return await self._exchange_microsoft(code, redirect_uri)
        return None

    async def _exchange_google(self, code: str, redirect_uri: str) -> SSOUserInfo | None:
        """Exchange Google OAuth code."""
        if not settings.sso_google_client_id or not settings.sso_google_client_secret:
            return None

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.sso_google_client_id,
                    "client_secret": settings.sso_google_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                return None

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            # Get user info
            user_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_response.status_code != 200:
                return None

            user_data = user_response.json()
            return SSOUserInfo(
                provider=SSOProvider.GOOGLE,
                provider_id=user_data["id"],
                email=user_data["email"],
                username=user_data.get("name", user_data["email"].split("@")[0]),
            )

    async def _exchange_github(self, code: str, redirect_uri: str) -> SSOUserInfo | None:
        """Exchange GitHub OAuth code."""
        if not settings.sso_github_client_id or not settings.sso_github_client_secret:
            return None

        async with httpx.AsyncClient() as client:
            # Exchange code for token
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": settings.sso_github_client_id,
                    "client_secret": settings.sso_github_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            if token_response.status_code != 200:
                return None

            tokens = token_response.json()
            access_token = tokens.get("access_token")
            if not access_token:
                return None

            # Get user info
            user_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if user_response.status_code != 200:
                return None

            user_data = user_response.json()

            # Get email (may need separate request)
            email = user_data.get("email")
            if not email:
                emails_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary_email = next(
                        (e["email"] for e in emails if e.get("primary")),
                        emails[0]["email"] if emails else None,
                    )
                    email = primary_email

            if not email:
                return None

            return SSOUserInfo(
                provider=SSOProvider.GITHUB,
                provider_id=str(user_data["id"]),
                email=email,
                username=user_data["login"],
            )

    async def _exchange_microsoft(self, code: str, redirect_uri: str) -> SSOUserInfo | None:
        """Exchange Microsoft OAuth code."""
        if not settings.sso_microsoft_client_id or not settings.sso_microsoft_client_secret:
            return None

        tenant = settings.sso_microsoft_tenant_id

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "client_id": settings.sso_microsoft_client_id,
                    "client_secret": settings.sso_microsoft_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": "openid email profile",
                },
            )
            if token_response.status_code != 200:
                return None

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            # Get user info
            user_response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_response.status_code != 200:
                return None

            user_data = user_response.json()
            email = user_data.get("mail") or user_data.get("userPrincipalName")

            return SSOUserInfo(
                provider=SSOProvider.MICROSOFT,
                provider_id=user_data["id"],
                email=email,
                username=user_data.get("displayName", email.split("@")[0] if email else "user"),
            )

    async def get_or_create_user(self, user_info: SSOUserInfo) -> User:
        """Get existing user or create a new one from SSO info."""
        # First try to find by email
        result = await self.db.execute(
            select(User).where(User.email == user_info.email)
        )
        user = result.scalar_one_or_none()

        if user:
            # Update auth method if needed
            if user.preferred_auth_method != AuthMethod.SSO:
                user.preferred_auth_method = AuthMethod.SSO
                await self.db.commit()
            return user

        # Try to find by username
        result = await self.db.execute(
            select(User).where(User.username == user_info.username)
        )
        existing = result.scalar_one_or_none()

        # Generate unique username if taken
        username = user_info.username
        if existing:
            username = f"{user_info.username}_{user_info.provider_id[:8]}"

        # Create new user
        user = User(
            id=uuid.uuid4(),
            username=username,
            email=user_info.email,
            preferred_auth_method=AuthMethod.SSO,
            is_active=True,
            is_superuser=False,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of configured SSO providers."""
        providers = []
        if settings.sso_google_client_id and settings.sso_google_client_secret:
            providers.append("google")
        if settings.sso_github_client_id and settings.sso_github_client_secret:
            providers.append("github")
        if settings.sso_microsoft_client_id and settings.sso_microsoft_client_secret:
            providers.append("microsoft")
        return providers
