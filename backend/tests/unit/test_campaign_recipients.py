"""
Unit tests for campaign-recipient sub-resource endpoints.

Routes tested
-------------
- GET    /campaigns/{id}/recipients
- POST   /campaigns/{id}/recipients
- DELETE /campaigns/{id}/recipients/{recipient_id}
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.enums import RecipientStatus
from app.features.campaigns import service as campaign_service
from app.features.recipients.schemas import RecipientResponse

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_CAMPAIGN_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
_RECIPIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")

_FAKE_RECIPIENT = RecipientResponse(
    id=_RECIPIENT_ID,
    email="alice@example.com",
    name="Alice",
    status=RecipientStatus.active,
    created_at=datetime(2026, 3, 11),
)


# ===========================================================================
# GET /campaigns/{id}/recipients
# ===========================================================================


class TestListCampaignRecipients:
    async def test_success_returns_200_with_list(self, authenticated_client):
        with patch.object(
            campaign_service,
            "list_campaign_recipients",
            new=AsyncMock(return_value=[_FAKE_RECIPIENT]),
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/recipients")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["email"] == "alice@example.com"
        assert data[0]["status"] == "active"

    async def test_empty_campaign_returns_empty_list(self, authenticated_client):
        with patch.object(
            campaign_service,
            "list_campaign_recipients",
            new=AsyncMock(return_value=[]),
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/recipients")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_campaign_not_found_returns_404(self, authenticated_client):
        with patch.object(
            campaign_service,
            "list_campaign_recipients",
            new=AsyncMock(
                side_effect=campaign_service.CampaignNotFoundError("Campaign not found")
            ),
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/recipients")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Campaign not found"

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get(f"/campaigns/{_CAMPAIGN_ID}/recipients")
        assert resp.status_code == 401


# ===========================================================================
# POST /campaigns/{id}/recipients
# ===========================================================================


class TestAddCampaignRecipient:
    async def test_success_returns_204_no_body(self, authenticated_client):
        with patch.object(
            campaign_service,
            "add_recipient_to_campaign",
            new=AsyncMock(return_value=None),
        ):
            resp = await authenticated_client.post(
                f"/campaigns/{_CAMPAIGN_ID}/recipients",
                json={"recipient_id": str(_RECIPIENT_ID)},
            )

        assert resp.status_code == 204
        assert resp.content == b""

    async def test_passes_correct_ids_to_service(self, authenticated_client):
        mock_add = AsyncMock(return_value=None)
        with patch.object(campaign_service, "add_recipient_to_campaign", new=mock_add):
            await authenticated_client.post(
                f"/campaigns/{_CAMPAIGN_ID}/recipients",
                json={"recipient_id": str(_RECIPIENT_ID)},
            )

        mock_add.assert_awaited_once()
        _db, _uid, cam_id, rec_id = mock_add.call_args.args
        assert cam_id == _CAMPAIGN_ID
        assert rec_id == _RECIPIENT_ID

    async def test_campaign_not_found_returns_404(self, authenticated_client):
        with patch.object(
            campaign_service,
            "add_recipient_to_campaign",
            new=AsyncMock(
                side_effect=campaign_service.CampaignNotFoundError("Campaign not found")
            ),
        ):
            resp = await authenticated_client.post(
                f"/campaigns/{_CAMPAIGN_ID}/recipients",
                json={"recipient_id": str(_RECIPIENT_ID)},
            )

        assert resp.status_code == 404

    async def test_duplicate_recipient_returns_409(self, authenticated_client):
        with patch.object(
            campaign_service,
            "add_recipient_to_campaign",
            new=AsyncMock(
                side_effect=campaign_service.CampaignConflictError(
                    "Recipient is already added to this campaign"
                )
            ),
        ):
            resp = await authenticated_client.post(
                f"/campaigns/{_CAMPAIGN_ID}/recipients",
                json={"recipient_id": str(_RECIPIENT_ID)},
            )

        assert resp.status_code == 409
        assert "already added" in resp.json()["detail"]

    async def test_missing_recipient_id_returns_422(self, authenticated_client):
        resp = await authenticated_client.post(
            f"/campaigns/{_CAMPAIGN_ID}/recipients", json={}
        )
        assert resp.status_code == 422

    async def test_invalid_recipient_uuid_returns_422(self, authenticated_client):
        resp = await authenticated_client.post(
            f"/campaigns/{_CAMPAIGN_ID}/recipients",
            json={"recipient_id": "not-a-uuid"},
        )
        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.post(
            f"/campaigns/{_CAMPAIGN_ID}/recipients",
            json={"recipient_id": str(_RECIPIENT_ID)},
        )
        assert resp.status_code == 401


# ===========================================================================
# DELETE /campaigns/{id}/recipients/{recipient_id}
# ===========================================================================


class TestRemoveCampaignRecipient:
    async def test_success_returns_204_no_body(self, authenticated_client):
        with patch.object(
            campaign_service,
            "remove_recipient_from_campaign",
            new=AsyncMock(return_value=None),
        ):
            resp = await authenticated_client.delete(
                f"/campaigns/{_CAMPAIGN_ID}/recipients/{_RECIPIENT_ID}"
            )

        assert resp.status_code == 204
        assert resp.content == b""

    async def test_recipient_not_in_campaign_returns_404(self, authenticated_client):
        with patch.object(
            campaign_service,
            "remove_recipient_from_campaign",
            new=AsyncMock(
                side_effect=campaign_service.CampaignNotFoundError(
                    "Recipient is not part of this campaign"
                )
            ),
        ):
            resp = await authenticated_client.delete(
                f"/campaigns/{_CAMPAIGN_ID}/recipients/{_RECIPIENT_ID}"
            )

        assert resp.status_code == 404
        assert "not part of this campaign" in resp.json()["detail"]

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.delete(
            f"/campaigns/{_CAMPAIGN_ID}/recipients/{_RECIPIENT_ID}"
        )
        assert resp.status_code == 401
