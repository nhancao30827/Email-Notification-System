import uuid
from base64 import b64decode
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import DeliveryStatus
from app.infrastructure.database.models.email_delivery import EmailDelivery
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/track", tags=["tracking"])

# Minimal 1×1 transparent GIF — standard tracking pixel payload
_PIXEL_GIF = b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@router.get("/open/{delivery_id}", include_in_schema=False)
async def track_open(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Record first open and return a 1×1 transparent GIF tracking pixel."""
    delivery = await db.scalar(
        select(EmailDelivery).where(EmailDelivery.id == delivery_id)
    )
    if delivery is not None and delivery.opened_at is None:
        delivery.opened_at = datetime.utcnow()
        delivery.status = DeliveryStatus.opened
    # Always return pixel — never leak whether the delivery_id is valid
    return Response(content=_PIXEL_GIF, media_type="image/gif")


@router.get("/click/{delivery_id}", include_in_schema=False)
async def track_click(
    delivery_id: uuid.UUID,
    url: str = Query(..., description="Destination URL"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Record first click and redirect to the original URL."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid redirect URL")
    delivery = await db.scalar(
        select(EmailDelivery).where(EmailDelivery.id == delivery_id)
    )
    if delivery is not None and delivery.clicked_at is None:
        delivery.clicked_at = datetime.utcnow()
        delivery.status = DeliveryStatus.clicked
    return RedirectResponse(url=url, status_code=302)
