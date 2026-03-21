import uuid
import base64
import binascii
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
    CsvBase64UploadRequest,
    CsvDeliveryTaskResponse,
    CsvDeliveryTaskStatusResponse,
    DeliveryResponse,
    DeliveryStatsResponse,
)
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/campaigns", tags=["email-deliveries"])


def _extract_csv_base64(payload: str) -> str:
    """Extract raw base64 content from plain or data URL payloads."""
    if "," in payload and payload.lower().startswith("data:"):
        return payload.split(",", 1)[1]
    return payload


@router.get("/{campaign_id}/deliveries", response_model=list[DeliveryResponse])
async def list_deliveries(
    campaign_id: uuid.UUID,
    status: Optional[DeliveryStatus] = Query(None, description="Filter by delivery status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List deliveries for a campaign, optionally filtered by status."""
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
    """Return aggregate delivery metrics for a campaign."""
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
    """Validate CSV upload and enqueue async delivery processing task."""
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


@router.post(
    "/{campaign_id}/deliveries/process-csv",
    response_model=CsvDeliveryTaskResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def enqueue_csv_delivery_task_base64(
    campaign_id: uuid.UUID,
    payload: CsvBase64UploadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue CSV processing from base64-encoded content."""
    encoded = _extract_csv_base64(payload.csv_content).strip()
    if not encoded:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="CSV base64 content is empty",
        )

    try:
        csv_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 CSV payload",
        )

    if not csv_bytes:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Decoded CSV content is empty",
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
            "csv_content": encoded,
        },
    )

    return CsvDeliveryTaskResponse(task_id=async_result.id, status="queued")


@router.get(
    "/deliveries/tasks/{task_id}",
    response_model=CsvDeliveryTaskStatusResponse,
)
async def get_csv_delivery_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return Celery task state and available CSV processing counters."""
    _ = current_user  # auth guard
    async_result = celery_app.AsyncResult(task_id)
    state = async_result.state.upper()

    if state == "SUCCESS":
        result = async_result.result if isinstance(async_result.result, dict) else {}
        return CsvDeliveryTaskStatusResponse(
            task_id=task_id,
            state=state,
            status=str(result.get("status", "completed")),
            processed=int(result.get("processed", 0) or 0),
            sent=int(result.get("sent", 0) or 0),
            failed=int(result.get("failed", 0) or 0),
            invalid_rows=int(result.get("invalid_rows", 0) or 0),
            error=result.get("error"),
        )

    if state == "FAILURE":
        return CsvDeliveryTaskStatusResponse(
            task_id=task_id,
            state=state,
            status="failed",
            error=str(async_result.result),
        )

    meta = async_result.info if isinstance(async_result.info, dict) else {}
    return CsvDeliveryTaskStatusResponse(
        task_id=task_id,
        state=state,
        status=str(meta.get("status", state.lower())),
        processed=int(meta.get("processed", 0) or 0),
        sent=int(meta.get("sent", 0) or 0),
        failed=int(meta.get("failed", 0) or 0),
        invalid_rows=int(meta.get("invalid_rows", 0) or 0),
        error=meta.get("error"),
    )
