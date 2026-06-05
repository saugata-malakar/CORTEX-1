"""
Cortex — api/routers/auth.py
Authentication endpoints.

POST /auth/register   → create org + admin user
POST /auth/login      → email/password → {access_token, refresh_token}
POST /auth/refresh    → rotate refresh token → new {access_token, refresh_token}
POST /auth/logout     → revoke all tokens for current user
GET  /auth/me         → current user profile
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    create_access_token,
    create_and_store_refresh_token,
    get_current_user,
    hash_password,
    revoke_all_user_tokens,
    rotate_refresh_token,
    verify_password,
)
from api.database import get_session
from api.models import AuditLog, Organization, User, UserRole

log = logging.getLogger("cortex.auth.router")
router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    org_name:   str = Field(..., min_length=2, max_length=200)
    org_slug:   str = Field(..., min_length=2, max_length=100,
                            pattern=r"^[a-z0-9\-]+$")
    email:      EmailStr
    password:   str = Field(..., min_length=8)
    full_name:  str = Field(..., min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = 900   # 15 min in seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id:        str
    org_id:    str
    email:     str
    full_name: str | None
    role:      str
    is_active: bool


# ─── POST /auth/register ──────────────────────────────────────────────────────

@router.post(
    "/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    summary="Register new organisation and admin user",
)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # Check slug uniqueness
    existing = await db.execute(
        select(Organization).where(Organization.slug == body.org_slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Organisation slug '{body.org_slug}' already taken",
        )

    # Check email uniqueness (global — emails unique per org, not globally, but
    # for first-time registration we treat as global to avoid confusion)
    existing_user = await db.execute(
        select(User).where(User.email == str(body.email))
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create org
    org = Organization(name=body.org_name, slug=body.org_slug)
    db.add(org)
    await db.flush()

    # Create admin user
    user = User(
        org_id=str(org.id),
        email=str(body.email),
        hashed_pw=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Audit
    db.add(AuditLog(
        org_id=str(org.id),
        user_id=str(user.id),
        action="org.registered",
        resource="organizations",
        resource_id=str(org.id),
        metadata_={"slug": body.org_slug},
    ))

    access_token  = create_access_token(user)
    refresh_token = await create_and_store_refresh_token(user, db)

    log.info(f"New org registered: {org.slug} user={user.email}")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ─── POST /auth/login ─────────────────────────────────────────────────────────

@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    result = await db.execute(
        select(User).where(
            User.email == str(body.email),
            User.deleted_at.is_(None),
        )
    )
    user: User | None = result.scalar_one_or_none()

    # Constant-time comparison regardless of whether user exists
    pw_valid = verify_password(body.password, user.hashed_pw) if user else False

    if not user or not pw_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Update last login
    from datetime import datetime
    user.last_login_at = datetime.utcnow()

    access_token  = create_access_token(user)
    refresh_token = await create_and_store_refresh_token(user, db)

    db.add(AuditLog(
        org_id=str(user.org_id),
        user_id=str(user.id),
        action="user.login",
        resource="users",
        resource_id=str(user.id),
        metadata_={},
    ))

    log.info(f"Login: {user.email} org={user.org_id}")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ─── POST /auth/refresh ───────────────────────────────────────────────────────

@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token",
)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user, new_refresh = await rotate_refresh_token(body.refresh_token, db)
    access_token = create_access_token(user)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


# ─── POST /auth/logout ────────────────────────────────────────────────────────

@router.post("/auth/logout", status_code=204, summary="Revoke all tokens")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await revoke_all_user_tokens(str(current_user.id), db)
    log.info(f"Logout: {current_user.email}")


# ─── GET /auth/me ─────────────────────────────────────────────────────────────

@router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return UserResponse(
        id=str(current_user.id),
        org_id=str(current_user.org_id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )
