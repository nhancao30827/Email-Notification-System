import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db
from app.infrastructure.redis.client import is_blacklisted

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except JWTError:
        raise exc

    if payload.get("type") != "access":
        raise exc

    jti: str | None = payload.get("jti")
    if not jti or await is_blacklisted(jti):
        raise exc

    user = await db.scalar(select(User).where(User.id == uuid.UUID(payload["sub"])))
    if user is None:
        raise exc
    return user
