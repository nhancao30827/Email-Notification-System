from datetime import UTC, datetime

from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.features.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.infrastructure.database.models.user import User
from app.infrastructure.redis.client import blacklist_token, is_blacklisted


class AuthError(Exception):
    pass


async def register(db: AsyncSession, data: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise AuthError("Email already registered")
    user = User(email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise AuthError("Invalid credentials")
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise AuthError("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise AuthError("Not a refresh token")

    jti: str | None = payload.get("jti")
    if not jti or await is_blacklisted(jti):
        raise AuthError("Token has been revoked")

    # Blacklist the used refresh token for its remaining TTL
    ttl = max(0, payload["exp"] - int(datetime.now(UTC).timestamp()))
    await blacklist_token(jti, ttl)

    access_token = create_access_token(payload["sub"])
    new_refresh = create_refresh_token(payload["sub"])
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


async def logout(access_token: str, refresh_token: str) -> None:
    now = int(datetime.now(UTC).timestamp())
    for token in (access_token, refresh_token):
        try:
            payload = decode_token(token)
            jti: str | None = payload.get("jti")
            if jti:
                ttl = max(0, payload["exp"] - now)
                await blacklist_token(jti, ttl)
        except JWTError:
            pass  # already expired — nothing to blacklist
