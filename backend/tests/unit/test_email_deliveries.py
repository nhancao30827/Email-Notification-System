"""
Unit tests for email delivery read-only endpoints.

Routes tested
-------------
- GET /campaigns/{id}/deliveries               (list, optional status filter)
- GET /campaigns/{id}/deliveries/stats         (aggregated counts)
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.enums import DeliveryStatus
from app.features.campaigns.service import CampaignNotFoundError
from app.features.email_deliveries import service as delivery_service
from app.features.email_deliveries.schemas import DeliveryResponse, DeliveryStatsResponse

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_CAMPAIGN_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
_RECIPIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")
_DELIVERY_ID = uuid.UUID("00000000-0000-0000-0000-000000000030")

_FAKE_DELIVERY = DeliveryResponse(
    id=_DELIVERY_ID,
    campaign_id=_CAMPAIGN_ID,
    recipient_id=_RECIPIENT_ID,
    status=DeliveryStatus.sent,
    sent_at=datetime(2026, 3, 11, 10, 0, 0),
    opened_at=None,
    clicked_at=None,
    error_message=None,
)

_FAKE_STATS = DeliveryStatsResponse(
    total=10,
    sent=6,
    opened=3,
    clicked=1,
    bounced=0,
    failed=0,
)


# ===========================================================================
# GET /campaigns/{id}/deliveries
# ===========================================================================


class TestListDeliveries:
    async def test_success_returns_200_with_list(self, authenticated_client):
        with patch.object(
            delivery_service,
            "list_deliveries",
            new=AsyncMock(return_value=[_FAKE_DELIVERY]),
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/deliveries")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["id"] == str(_DELIVERY_ID)
        assert data[0]["status"] == "sent"

    async def test_empty_list_returns_200(self, authenticated_client):
        with patch.object(
            delivery_service, "list_deliveries", new=AsyncMock(return_value=[])
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/deliveries")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_status_filter_passed_to_service(self, authenticated_client):
        mock_list = AsyncMock(return_value=[_FAKE_DELIVERY])
        with patch.object(delivery_service, "list_deliveries", new=mock_list):
            await authenticated_client.get(
                f"/campaigns/{_CAMPAIGN_ID}/deliveries?status=sent"
            )

        mock_list.assert_awaited_once()
        _db, _uid, _cid, status_arg = mock_list.call_args.args
        assert status_arg == DeliveryStatus.sent

    async def test_no_filter_passes_none_to_service(self, authenticated_client):
        mock_list = AsyncMock(return_value=[])
        with patch.object(delivery_service, "list_deliveries", new=mock_list):
            await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/deliveries")

        _db, _uid, _cid, status_arg = mock_list.call_args.args
        assert status_arg is None

    async def test_all_valid_statuses_accepted(self, authenticated_client):
        for status in DeliveryStatus:
            with patch.object(
                delivery_service, "list_deliveries", new=AsyncMock(return_value=[])
            ):
                resp = await authenticated_client.get(
                    f"/campaigns/{_CAMPAIGN_ID}/deliveries?status={status.value}"
                )
            assert resp.status_code == 200

    async def test_invalid_status_filter_returns_422(self, authenticated_client):
        resp = await authenticated_client.get(
            f"/campaigns/{_CAMPAIGN_ID}/deliveries?status=invalid"
        )
        assert resp.status_code == 422

    async def test_campaign_not_found_returns_404(self, authenticated_client):
        with patch.object(
            delivery_service,
            "list_deliveries",
            new=AsyncMock(side_effect=CampaignNotFoundError("Campaign not found")),
        ):
            resp = await authenticated_client.get(f"/campaigns/{_CAMPAIGN_ID}/deliveries")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Campaign not found"

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get(f"/campaigns/{_CAMPAIGN_ID}/deliveries")
        assert resp.status_code == 401


# ===========================================================================
# GET /campaigns/{id}/deliveries/stats
# ===========================================================================


class TestGetDeliveryStats:
    async def test_success_returns_200_with_stats(self, authenticated_client):
        with patch.object(
            delivery_service,
            "get_delivery_stats",
            new=AsyncMock(return_value=_FAKE_STATS),
        ):
            resp = await authenticated_client.get(
                f"/campaigns/{_CAMPAIGN_ID}/deliveries/stats"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert body["sent"] == 6
        assert body["opened"] == 3
        assert body["clicked"] == 1
        assert body["bounced"] == 0
        assert body["failed"] == 0

    async def test_zero_stats_for_new_campaign(self, authenticated_client):
        zero_stats = DeliveryStatsResponse(
            total=0, sent=0, opened=0, clicked=0, bounced=0, failed=0
        )
        with patch.object(
            delivery_service,
            "get_delivery_stats",
            new=AsyncMock(return_value=zero_stats),
        ):
            resp = await authenticated_client.get(
                f"/campaigns/{_CAMPAIGN_ID}/deliveries/stats"
            )

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_campaign_not_found_returns_404(self, authenticated_client):
        with patch.object(
            delivery_service,
            "get_delivery_stats",
            new=AsyncMock(side_effect=CampaignNotFoundError("Campaign not found")),
        ):
            resp = await authenticated_client.get(
                f"/campaigns/{_CAMPAIGN_ID}/deliveries/stats"
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Campaign not found"

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get(f"/campaigns/{_CAMPAIGN_ID}/deliveries/stats")
        assert resp.status_code == 401
