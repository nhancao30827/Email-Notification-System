"""
Shared pytest fixtures.

Environment variables MUST be set before any app module is imported so that
`app.core.config.settings` (which is instantiated at module level) resolves them
correctly.  We use os.environ.setdefault so that a real .env file can still
override these values when running outside the test suite.
"""

import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/testdb")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-32-chars!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

# Import only after env vars are in place.
from main import app  # noqa: E402
from app.core.dependencies import get_current_user  # noqa: E402
from app.infrastructure.database.models.user import User  # noqa: E402
from app.infrastructure.database.session import get_db  # noqa: E402

FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture()
async def client():
    """
    Async HTTP test client.

    - Overrides the ``get_db`` dependency with a no-op async generator so no
      real database connection is needed.
    - Patches ``init_redis`` / ``close_redis`` so the lifespan hook does not
      attempt to open a real Redis connection.
    """

    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db

    with (
        patch("app.infrastructure.redis.client.init_redis", new_callable=AsyncMock),
        patch("app.infrastructure.redis.client.close_redis", new_callable=AsyncMock),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest.fixture()
async def authenticated_client(client):
    """
    Client with ``get_current_user`` overridden to return a fake user.
    Eliminates the need for a real JWT or Redis in tests for protected routes.
    """
    fake_user = MagicMock(spec=User)
    fake_user.id = FAKE_USER_ID
    fake_user.email = "user@example.com"
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield client
    # app.dependency_overrides.clear() is called by the parent `client` fixture
