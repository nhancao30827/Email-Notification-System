import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import DeliveryStatus
from app.features.campaigns.service import CampaignNotFoundError, get_campaign
from app.features.email_deliveries.schemas import DeliveryStatsResponse
from app.infrastructure.database.models.email_delivery import EmailDelivery


async def list_deliveries(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
    status_filter: Optional[DeliveryStatus] = None,
) -> list[EmailDelivery]:
    await get_campaign(db, user_id, campaign_id)  # ownership check
    query = select(EmailDelivery).where(EmailDelivery.campaign_id == campaign_id)
    if status_filter is not None:
        query = query.where(EmailDelivery.status == status_filter)
    rows = await db.scalars(query)
    return list(rows.all())


async def get_delivery_stats(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> DeliveryStatsResponse:
    await get_campaign(db, user_id, campaign_id)  # ownership check

    base = select(func.count(EmailDelivery.id)).where(
        EmailDelivery.campaign_id == campaign_id
    )

    def count_for(s: DeliveryStatus):
        return base.where(EmailDelivery.status == s)

    total = await db.scalar(base) or 0
    sent = await db.scalar(count_for(DeliveryStatus.sent)) or 0
    opened = await db.scalar(count_for(DeliveryStatus.opened)) or 0
    clicked = await db.scalar(count_for(DeliveryStatus.clicked)) or 0
    bounced = await db.scalar(count_for(DeliveryStatus.bounced)) or 0
    failed = await db.scalar(count_for(DeliveryStatus.failed)) or 0

    return DeliveryStatsResponse(
        total=total,
        sent=sent,
        opened=opened,
        clicked=clicked,
        bounced=bounced,
        failed=failed,
    )
