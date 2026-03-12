"""
Unit tests for recipient CRUD endpoints.

Routes tested
-------------
- POST   /recipients
- GET    /recipients
- GET    /recipients/{recipient_id}
- PATCH  /recipients/{recipient_id}
- DELETE /recipients/{recipient_id}
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.enums import RecipientStatus
from app.features.recipients import service as recipient_service
from app.features.recipients.schemas import RecipientResponse

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_RECIPIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")

_FAKE_RECIPIENT = RecipientResponse(
    id=_RECIPIENT_ID,
    email="alice@example.com",
    name="Alice",
    status=RecipientStatus.active,
    created_at=datetime(2026, 3, 11),
)

_CREATE_BODY = {"email": "alice@example.com", "name": "Alice"}


# ===========================================================================
# POST /recipients
# ===========================================================================


class TestCreateRecipient:
    async def test_success_returns_201_with_recipient(self, authenticated_client):
        with patch.object(
            recipient_service,
            "create_recipient",
            new=AsyncMock(return_value=_FAKE_RECIPIENT),
        ):
            resp = await authenticated_client.post("/recipients", json=_CREATE_BODY)

        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "alice@example.com"
        assert body["name"] == "Alice"
        assert body["status"] == "active"

    async def test_passes_data_to_service(self, authenticated_client):
        mock_create = AsyncMock(return_value=_FAKE_RECIPIENT)
        with patch.object(recipient_service, "create_recipient", new=mock_create):
            await authenticated_client.post("/recipients", json=_CREATE_BODY)

        mock_create.assert_awaited_once()
        _db, _uid, data_arg = mock_create.call_args.args
        assert data_arg.email == "alice@example.com"
        assert data_arg.name == "Alice"

    async def test_duplicate_email_returns_409(self, authenticated_client):
        with patch.object(
            recipient_service,
            "create_recipient",
            new=AsyncMock(
                side_effect=recipient_service.RecipientConflictError(
                    "Recipient with this email already exists"
                )
            ),
        ):
            resp = await authenticated_client.post("/recipients", json=_CREATE_BODY)

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    async def test_missing_email_returns_422(self, authenticated_client):
        resp = await authenticated_client.post("/recipients", json={"name": "Alice"})
        assert resp.status_code == 422

    async def test_invalid_email_format_returns_422(self, authenticated_client):
        resp = await authenticated_client.post(
            "/recipients", json={"email": "not-an-email"}
        )
        assert resp.status_code == 422

    async def test_name_is_optional(self, authenticated_client):
        with patch.object(
            recipient_service,
            "create_recipient",
            new=AsyncMock(
                return_value=_FAKE_RECIPIENT.model_copy(update={"name": None})
            ),
        ):
            resp = await authenticated_client.post(
                "/recipients", json={"email": "alice@example.com"}
            )

        assert resp.status_code == 201

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.post("/recipients", json=_CREATE_BODY)
        assert resp.status_code == 401


# ===========================================================================
# GET /recipients
# ===========================================================================


class TestListRecipients:
    async def test_success_returns_200_with_list(self, authenticated_client):
        with patch.object(
            recipient_service,
            "list_recipients",
            new=AsyncMock(return_value=[_FAKE_RECIPIENT]),
        ):
            resp = await authenticated_client.get("/recipients")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["id"] == str(_RECIPIENT_ID)

    async def test_empty_list_returns_200(self, authenticated_client):
        with patch.object(
            recipient_service, "list_recipients", new=AsyncMock(return_value=[])
        ):
            resp = await authenticated_client.get("/recipients")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get("/recipients")
        assert resp.status_code == 401


# ===========================================================================
# GET /recipients/{recipient_id}
# ===========================================================================


class TestGetRecipient:
    async def test_success_returns_200(self, authenticated_client):
        with patch.object(
            recipient_service,
            "get_recipient",
            new=AsyncMock(return_value=_FAKE_RECIPIENT),
        ):
            resp = await authenticated_client.get(f"/recipients/{_RECIPIENT_ID}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(_RECIPIENT_ID)

    async def test_not_found_returns_404(self, authenticated_client):
        with patch.object(
            recipient_service,
            "get_recipient",
            new=AsyncMock(
                side_effect=recipient_service.RecipientNotFoundError("Recipient not found")
            ),
        ):
            resp = await authenticated_client.get(f"/recipients/{_RECIPIENT_ID}")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Recipient not found"

    async def test_invalid_uuid_returns_422(self, authenticated_client):
        resp = await authenticated_client.get("/recipients/not-a-uuid")
        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get(f"/recipients/{_RECIPIENT_ID}")
        assert resp.status_code == 401


# ===========================================================================
# PATCH /recipients/{recipient_id}
# ===========================================================================


class TestUpdateRecipient:
    async def test_success_returns_200(self, authenticated_client):
        updated = _FAKE_RECIPIENT.model_copy(update={"name": "Alice Smith"})
        with patch.object(
            recipient_service,
            "update_recipient",
            new=AsyncMock(return_value=updated),
        ):
            resp = await authenticated_client.patch(
                f"/recipients/{_RECIPIENT_ID}", json={"name": "Alice Smith"}
            )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice Smith"

    async def test_update_status(self, authenticated_client):
        updated = _FAKE_RECIPIENT.model_copy(update={"status": RecipientStatus.unsubscribed})
        with patch.object(
            recipient_service,
            "update_recipient",
            new=AsyncMock(return_value=updated),
        ):
            resp = await authenticated_client.patch(
                f"/recipients/{_RECIPIENT_ID}", json={"status": "unsubscribed"}
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "unsubscribed"

    async def test_not_found_returns_404(self, authenticated_client):
        with patch.object(
            recipient_service,
            "update_recipient",
            new=AsyncMock(
                side_effect=recipient_service.RecipientNotFoundError("Recipient not found")
            ),
        ):
            resp = await authenticated_client.patch(
                f"/recipients/{_RECIPIENT_ID}", json={"name": "X"}
            )

        assert resp.status_code == 404

    async def test_invalid_status_value_returns_422(self, authenticated_client):
        resp = await authenticated_client.patch(
            f"/recipients/{_RECIPIENT_ID}", json={"status": "invalid_status"}
        )
        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.patch(f"/recipients/{_RECIPIENT_ID}", json={"name": "X"})
        assert resp.status_code == 401


# ===========================================================================
# DELETE /recipients/{recipient_id}
# ===========================================================================


class TestDeleteRecipient:
    async def test_success_returns_204_no_body(self, authenticated_client):
        with patch.object(
            recipient_service,
            "delete_recipient",
            new=AsyncMock(return_value=None),
        ):
            resp = await authenticated_client.delete(f"/recipients/{_RECIPIENT_ID}")

        assert resp.status_code == 204
        assert resp.content == b""

    async def test_not_found_returns_404(self, authenticated_client):
        with patch.object(
            recipient_service,
            "delete_recipient",
            new=AsyncMock(
                side_effect=recipient_service.RecipientNotFoundError("Recipient not found")
            ),
        ):
            resp = await authenticated_client.delete(f"/recipients/{_RECIPIENT_ID}")

        assert resp.status_code == 404

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.delete(f"/recipients/{_RECIPIENT_ID}")
        assert resp.status_code == 401
