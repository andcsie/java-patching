"""Authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AuthServiceDep, CurrentUser, DbSession, get_auth_service
from app.core.security import AuthMethod
from app.schemas.user import (
    SSHChallengeRequest,
    SSHChallengeResponse,
    SSHVerifyRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """Register a new user."""
    existing = await auth_service.get_user_by_username(user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    user = await auth_service.create_user(user_data)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    auth_service: AuthServiceDep,
) -> Token:
    """Login with username and password."""
    user = await auth_service.authenticate_password(
        credentials.username,
        credentials.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await auth_service.create_tokens(user)


@router.post("/ssh/challenge", response_model=SSHChallengeResponse)
async def ssh_challenge(
    request: SSHChallengeRequest,
    auth_service: AuthServiceDep,
) -> SSHChallengeResponse:
    """Request an SSH authentication challenge."""
    result = await auth_service.generate_ssh_challenge(request.username)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or SSH key not configured",
        )

    challenge, expires_at = result
    return SSHChallengeResponse(challenge=challenge, expires_at=expires_at)


@router.post("/ssh/verify", response_model=Token)
async def ssh_verify(
    request: SSHVerifyRequest,
    auth_service: AuthServiceDep,
) -> Token:
    """Verify SSH signature and login."""
    user = await auth_service.authenticate_ssh(
        request.username,
        request.challenge,
        request.signature,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SSH authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await auth_service.create_tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    auth_service: AuthServiceDep,
) -> Token:
    """Refresh access token."""
    tokens = await auth_service.refresh_access_token(refresh_token)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return tokens


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """Update current user information."""
    if user_update.password:
        await auth_service.update_password(current_user, user_update.password)

    if user_update.ssh_public_key:
        success = await auth_service.update_ssh_key(
            current_user,
            user_update.ssh_public_key,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SSH public key format",
            )

    if user_update.preferred_auth_method:
        success = await auth_service.switch_auth_method(
            current_user,
            user_update.preferred_auth_method,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot switch to auth method that is not configured",
            )

    if user_update.email:
        current_user.email = user_update.email

    return UserResponse.model_validate(current_user)


@router.post("/me/switch-auth-method", response_model=UserResponse)
async def switch_auth_method(
    method: AuthMethod,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """Switch preferred authentication method."""
    success = await auth_service.switch_auth_method(current_user, method)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot switch to {method}: not configured",
        )
    return UserResponse.model_validate(current_user)
