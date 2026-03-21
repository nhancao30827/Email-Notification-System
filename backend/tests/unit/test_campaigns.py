"""
Unit tests for campaign CRUD endpoints.

Strategy
--------
* Service layer is fully mocked — no DB or Redis connections needed.
* ``authenticated_client`` fixture provides a pre-authenticated HTTP client.
* Unauthenticated cases use the plain ``client`` fixture (no Bearer header →
  HTTPBearer raises 403).
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.enums import CampaignStatus
from app.features.campaigns import service as campaign_service
from app.features.campaigns.schemas import CampaignResponse

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_CAMPAIGN_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")

_FAKE_CAMPAIGN = CampaignResponse(
    id=_CAMPAIGN_ID,
    name="Welcome Campaign",
    subject="Hello there",
    body="Welcome to our platform!",
    status=CampaignStatus.draft,
    scheduled_at=None,
    sent_at=None,
    created_at=datetime(2026, 3, 11),
)

_CREATE_BODY = {
    "name": "Welcome Campaign",
    "subject": "Hello there",
    "body": "Welcome to our platform!",
}


# ===========================================================================
# POST /campaigns
# ===========================================================================


class TestCreateCampaign:
    async def test_success_returns_201_with_campaign(self, authenticated_client):
        with patch.object(
            campaign_service, "create_campaign", new=AsyncMock(return_value=_FAKE_CAMPAIGN)
        ):
            resp = await authenticated_client.post("/campaigns", json=_CREATE_BODY)

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Welcome Campaign"
        assert body["subject"] == "Hello there"
        assert body["status"] == "draft"

    async def test_passes_data_to_service(self, authenticated_client):
        mock_create = AsyncMock(return_value=_FAKE_CAMPAIGN)
        with patch.object(campaign_service, "create_campaign", new=mock_create):
            await authenticated_client.post("/campaigns", json=_CREATE_BODY)

        mock_create.assert_awaited_once()
        _db, _uid, data_arg = mock_create.call_args.args
        assert data_arg.name == "Welcome Campaign"
        assert data_arg.subject == "Hello there"

    async def test_missing_name_returns_422(self, authenticated_client):
        resp = await authenticated_client.post(
            "/campaigns", json={"subject": "Hi", "body": "Body"}
        )
        assert resp.status_code == 422

    async def test_missing_subject_returns_422(self, authenticated_client):
        resp = await authenticated_client.post(
            "/campaigns", json={"name": "Campaign", "body": "Body"}
        )
        assert resp.status_code == 422

    async def test_missing_body_returns_422(self, authenticated_client):
        resp = await authenticated_client.post(
            "/campaigns", json={"name": "Campaign", "subject": "Hi"}
        )
        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.post("/campaigns", json=_CREATE_BODY)
        assert resp.status_code == 401


# ===========================================================================
# GET /campaigns
# ===========================================================================


class TestListCampaigns:
    async def test_success_returns_200_with_list(self, authenticated_client):
        with patch.object(
            campaign_service, "list_campaigns", new=AsyncMock(return_value=[_FAKE_CAMPAIGN])
        ):
            resp = await authenticated_client.get("/campaigns")

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert resp.json()[0]["id"] == str(_CAMPAIGN_ID)

    async def test_empty_list_returns_200(self, authenticated_client):
        with patch.object(
            campaign_service, "list_campaigns", new=AsyncMock(return_value=[])
        ):
            resp = await authenticated_client.get("/campaigns")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get("/campaigns")
        assert resp.status_code == 401


# ===========================================================================
# GET /campaigns/{campaign_id}
# ===========================================================================


class TestGetCampaign:
    async def test_success_returns_200(self, authenticated_client):
        with patch.object(
            campaign_service, "get_campaign", new=AsyncMock(return_value=_FAKE_CAMPAIGN)
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(_CAMPAIGN_ID)

    async def test_not_found_returns_404(self, authenticated_client):
        with patch.object(
            campaign_service,
            "get_campaign",
            new=AsyncMock(side_effect=campaign_service.CampaignNotFoundError("Campaign not found")),
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Campaign not found"

    async def test_invalid_uuid_returns_422(self, authenticated_client):
        resp = await authenticated_client.get("/campaigns/not-a-uuid")
        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get(f"/campaigns/{_CAMPAIGN_ID}")
        assert resp.status_code == 401


# ===========================================================================
# PATCH /campaigns/{campaign_id}
# ===========================================================================


class TestUpdateCampaign:
    async def test_success_returns_200(self, authenticated_client):
        updated = _FAKE_CAMPAIGN.model_copy(update={"name": "Updated Name"})
        with patch.object(
            campaign_service, "update_campaign", new=AsyncMock(return_value=updated)
        ):
            resp = await authenticated_client.patch(
                f"/campaigns/{_CAMPAIGN_ID}", json={"name": "Updated Name"}
            )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_not_found_returns_404(self, authenticated_client):
        with patch.object(
            campaign_service,
            "update_campaign",
            new=AsyncMock(side_effect=campaign_service.CampaignNotFoundError("Campaign not found")),
        ):
            resp = await authenticated_client.patch(
                f"/campaigns/{_CAMPAIGN_ID}", json={"name": "New Name"}
            )

        assert resp.status_code == 404

    async def test_non_draft_status_returns_409(self, authenticated_client):
        with patch.object(
            campaign_service,
            "update_campaign",
            new=AsyncMock(
                side_effect=campaign_service.CampaignConflictError("Only draft campaigns can be updated")
            ),
        ):
            resp = await authenticated_client.patch(
                f"/campaigns/{_CAMPAIGN_ID}", json={"name": "New Name"}
            )

        assert resp.status_code == 409
        assert "draft" in resp.json()["detail"]

    async def test_empty_patch_body_accepted(self, authenticated_client):
        with patch.object(
            campaign_service, "update_campaign", new=AsyncMock(return_value=_FAKE_CAMPAIGN)
        ):
            resp = await authenticated_client.patch(f"/campaigns/{_CAMPAIGN_ID}", json={})

        assert resp.status_code == 200

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.patch(f"/campaigns/{_CAMPAIGN_ID}", json={"name": "X"})
        assert resp.status_code == 401


# ===========================================================================
# DELETE /campaigns/{campaign_id}
# ===========================================================================


class TestDeleteCampaign:
    async def test_success_returns_204_no_body(self, authenticated_client):
        with patch.object(
            campaign_service, "delete_campaign", new=AsyncMock(return_value=None)
        ):
            resp = await authenticated_client.delete(f"/campaigns/{_CAMPAIGN_ID}")

        assert resp.status_code == 204
        assert resp.content == b""

    async def test_not_found_returns_404(self, authenticated_client):
        with patch.object(
            campaign_service,
            "delete_campaign",
            new=AsyncMock(side_effect=campaign_service.CampaignNotFoundError("Campaign not found")),
        ):
            resp = await authenticated_client.delete(f"/campaigns/{_CAMPAIGN_ID}")

        assert resp.status_code == 404

    async def test_non_deletable_status_returns_409(self, authenticated_client):
        with patch.object(
            campaign_service,
            "delete_campaign",
            new=AsyncMock(
                side_effect=campaign_service.CampaignConflictError(
                    "Only draft or cancelled campaigns can be deleted"
                )
            ),
        ):
            resp = await authenticated_client.delete(f"/campaigns/{_CAMPAIGN_ID}")

        assert resp.status_code == 409

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.delete(f"/campaigns/{_CAMPAIGN_ID}")
        assert resp.status_code == 401
