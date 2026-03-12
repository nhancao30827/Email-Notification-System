"""
Tests for POST /auth/login and POST /auth/logout.

Strategy
--------
* The service layer (DB queries, Redis calls) is fully mocked so the tests
  exercise only the HTTP routing and status-code/body contract.
* ``app.features.auth.service.login`` and ``service.logout`` are patched per
  test via ``unittest.mock.patch``.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.features.auth import service as auth_service
from app.features.auth.schemas import TokenResponse

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_VALID_TOKENS = TokenResponse(
    access_token="header.payload.access",
    refresh_token="header.payload.refresh",
)
_VALID_LOGIN_BODY = {"email": "user@example.com", "password": "s3cr3t"}
_BEARER_HEADER = {"Authorization": "Bearer header.payload.access"}


# ===========================================================================
# POST /auth/login
# ===========================================================================


class TestLogin:
    """Tests for POST /auth/login."""

    # ── happy path ──────────────────────────────────────────────────────────

    async def test_success_returns_200_with_token_response(self, client):
        """Valid credentials → 200 with access & refresh tokens."""
        with patch.object(
            auth_service, "login", new=AsyncMock(return_value=_VALID_TOKENS)
        ):
            resp = await client.post("/auth/login", json=_VALID_LOGIN_BODY)

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "header.payload.access"
        assert body["refresh_token"] == "header.payload.refresh"
        assert body["token_type"] == "bearer"

    async def test_success_passes_credentials_to_service(self, client):
        """The endpoint must forward the request email/password to the service."""
        mock_login = AsyncMock(return_value=_VALID_TOKENS)
        with patch.object(auth_service, "login", new=mock_login):
            await client.post("/auth/login", json=_VALID_LOGIN_BODY)

        mock_login.assert_awaited_once()
        _db_arg, request_arg = mock_login.call_args.args
        assert request_arg.email == "user@example.com"
        assert request_arg.password == "s3cr3t"

    # ── error path ───────────────────────────────────────────────────────────

    async def test_invalid_credentials_returns_401(self, client):
        """AuthError from service → 401 Unauthorized with WWW-Authenticate header."""
        with patch.object(
            auth_service,
            "login",
            new=AsyncMock(side_effect=auth_service.AuthError("bad creds")),
        ):
            resp = await client.post("/auth/login", json=_VALID_LOGIN_BODY)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"
        assert resp.headers.get("www-authenticate") == "Bearer"

    # ── validation ───────────────────────────────────────────────────────────

    async def test_missing_email_returns_422(self, client):
        resp = await client.post("/auth/login", json={"password": "s3cr3t"})
        assert resp.status_code == 422

    async def test_missing_password_returns_422(self, client):
        resp = await client.post(
            "/auth/login", json={"email": "user@example.com"}
        )
        assert resp.status_code == 422

    async def test_invalid_email_format_returns_422(self, client):
        resp = await client.post(
            "/auth/login",
            json={"email": "not-an-email", "password": "s3cr3t"},
        )
        assert resp.status_code == 422

    async def test_empty_body_returns_422(self, client):
        resp = await client.post("/auth/login", json={})
        assert resp.status_code == 422

    async def test_no_body_returns_422(self, client):
        resp = await client.post("/auth/login")
        assert resp.status_code == 422


# ===========================================================================
# POST /auth/logout
# ===========================================================================


class TestLogout:
    """Tests for POST /auth/logout."""

    # ── happy path ──────────────────────────────────────────────────────────

    async def test_success_returns_204_no_body(self, client):
        """Valid access token + refresh token → 204 with empty body."""
        with patch.object(
            auth_service, "logout", new=AsyncMock(return_value=None)
        ):
            resp = await client.post(
                "/auth/logout",
                json={"refresh_token": "header.payload.refresh"},
                headers=_BEARER_HEADER,
            )

        assert resp.status_code == 204
        assert resp.content == b""

    async def test_success_passes_both_tokens_to_service(self, client):
        """Router must forward access token (header) and refresh token (body) to service."""
        mock_logout = AsyncMock(return_value=None)
        with patch.object(auth_service, "logout", new=mock_logout):
            await client.post(
                "/auth/logout",
                json={"refresh_token": "my-refresh-token"},
                headers={"Authorization": "Bearer my-access-token"},
            )

        mock_logout.assert_awaited_once_with("my-access-token", "my-refresh-token")

    # ── missing / malformed inputs ───────────────────────────────────────────

    async def test_missing_authorization_header_returns_401(self, client):
        """HTTPBearer raises 401 when no Authorization header is provided."""
        resp = await client.post(
            "/auth/logout",
            json={"refresh_token": "header.payload.refresh"},
        )
        assert resp.status_code == 401

    async def test_missing_refresh_token_in_body_returns_422(self, client):
        """Request body without refresh_token fails Pydantic validation."""
        resp = await client.post(
            "/auth/logout",
            json={},
            headers=_BEARER_HEADER,
        )
        assert resp.status_code == 422

    async def test_empty_body_returns_422(self, client):
        resp = await client.post("/auth/logout", headers=_BEARER_HEADER)
        assert resp.status_code == 422

    async def test_non_bearer_scheme_returns_401(self, client):
        """Only Bearer tokens are accepted by HTTPBearer."""
        resp = await client.post(
            "/auth/logout",
            json={"refresh_token": "header.payload.refresh"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401
