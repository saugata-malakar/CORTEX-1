"""
Cortex — api/auth.py
JWT authentication + RBAC.

Token strategy:
  - Access token:  short-lived (15 min), stateless JWT
  - Refresh token: long-lived (30 days), stored hash in DB, rotated on use
  - Organisation claim in every token → enforces multitenancy at query layer

RBAC:
  ADMIN    → all operations within their org
  ENGINEER → read + write inspections/buildings; no user management
  VIEWER   → read-only across all resources

Dependencies (FastAPI):
  get_current_user   → any authenticated user
  require_engineer   → ENGINEER or ADMIN
  require_admin      → ADMIN only
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_session
from api.models import RefreshToken, User, UserRole

log = logging.getLogger("cortex.auth")

security = HTTPBearer(auto_error=True)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30


# ─── Password hashing ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ─── Token creation ──────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    payload = {
        "sub":     str(user.id),
        "org_id":  str(user.org_id),
        "role":    user.role.value,
        "email":   user.email,
        "type":    "access",
        "exp":     datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat":     datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store only the hash."""
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── Token decoding ──────────────────────────────────────────────────────────

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ─── FastAPI dependencies ─────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Validates Bearer JWT and returns the User ORM object.
    Raises 401 if token is invalid/expired.
    Raises 403 if user is inactive or soft-deleted.
    """
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    return user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory for role-based access.

    Usage:
        @router.post("/admin-only")
        async def handler(user = Depends(require_admin)):
            ...
    """
    async def _check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in allowed_roles]}",
            )
        return user
    return _check


require_engineer = require_role(UserRole.ENGINEER, UserRole.ADMIN)
require_admin    = require_role(UserRole.ADMIN)


# ─── Org scope enforcement ────────────────────────────────────────────────────

def assert_org_access(user: User, resource_org_id: str):
    """
    Raises 403 if the user tries to access a resource outside their org.
    Call this in every endpoint that fetches by resource ID.
    """
    if str(user.org_id) != str(resource_org_id):
        log.warning(
            f"Org access violation: user={user.id} org={user.org_id} "
            f"tried to access resource in org={resource_org_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


# ─── Refresh token lifecycle ──────────────────────────────────────────────────

async def create_and_store_refresh_token(
    user: User,
    db: AsyncSession,
) -> str:
    """Creates, stores, and returns the raw refresh token."""
    raw, hashed = create_refresh_token()
    token_record = RefreshToken(
        user_id=str(user.id),
        token_hash=hashed,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(token_record)
    await db.flush()
    return raw


async def rotate_refresh_token(
    raw_token: str,
    db: AsyncSession,
) -> tuple[User, str]:
    """
    Validates old refresh token, rotates it, returns (user, new_raw_token).
    Raises 401 on invalid/expired/revoked token.
    """
    token_hash = _hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > datetime.utcnow(),
        )
    )
    record: RefreshToken | None = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=401, detail="Refresh token invalid or expired")

    # Revoke old token
    record.revoked = True
    await db.flush()

    # Fetch user
    user_result = await db.execute(
        select(User).where(User.id == record.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    # Issue new token
    new_raw = await create_and_store_refresh_token(user, db)
    return user, new_raw


async def revoke_all_user_tokens(user_id: str, db: AsyncSession) -> None:
    """Logout everywhere — revoke all active refresh tokens for a user."""
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
