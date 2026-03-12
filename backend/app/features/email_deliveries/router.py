import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.domain.enums import DeliveryStatus
from app.features.campaigns.service import CampaignNotFoundError
from app.features.email_deliveries import service
from app.features.email_deliveries.schemas import DeliveryResponse, DeliveryStatsResponse
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/campaigns", tags=["email-deliveries"])


@router.get("/{campaign_id}/deliveries", response_model=list[DeliveryResponse])
async def list_deliveries(
    campaign_id: uuid.UUID,
    status: Optional[DeliveryStatus] = Query(None, description="Filter by delivery status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.list_deliveries(db, current_user.id, campaign_id, status)
    except CampaignNotFoundError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{campaign_id}/deliveries/stats", response_model=DeliveryStatsResponse)
async def get_delivery_stats(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.get_delivery_stats(db, current_user.id, campaign_id)
    except CampaignNotFoundError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
