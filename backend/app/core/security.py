import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _make_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    payload = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "type": token_type,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str) -> str:
    return _make_token(
        subject,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    return _make_token(
        subject,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])  # type: ignore[return-value]
