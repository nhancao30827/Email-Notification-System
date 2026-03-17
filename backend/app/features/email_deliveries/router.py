import uuid
import base64
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.dependencies import get_current_user
from app.domain.enums import DeliveryStatus
from app.features.campaigns import service as campaign_service
from app.features.campaigns.service import CampaignNotFoundError
from app.features.email_deliveries import service
from app.features.email_deliveries.schemas import (
    CsvDeliveryTaskResponse,
    DeliveryResponse,
    DeliveryStatsResponse,
)
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


@router.post(
    "/{campaign_id}/deliveries/upload-csv",
    response_model=CsvDeliveryTaskResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def enqueue_csv_delivery_task(
    campaign_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are supported",
        )

    csv_bytes = await file.read()
    if not csv_bytes:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty",
        )

    try:
        csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="CSV file must be UTF-8 encoded",
        )

    try:
        await campaign_service.get_campaign(db, current_user.id, campaign_id)
    except CampaignNotFoundError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))

    async_result = celery_app.send_task(
        "process_campaign_csv_task",
        kwargs={
            "campaign_id": str(campaign_id),
            "user_id": str(current_user.id),
            "csv_content": base64.b64encode(csv_bytes).decode("ascii"),
        },
    )

    return CsvDeliveryTaskResponse(task_id=async_result.id, status="queued")
