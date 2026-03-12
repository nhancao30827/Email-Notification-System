import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CampaignStatus
from app.features.campaigns.schemas import CampaignCreate, CampaignUpdate
from app.infrastructure.database.models.campaign import Campaign
from app.infrastructure.database.models.campaign_recipient import CampaignRecipient
from app.infrastructure.database.models.recipient import Recipient


class CampaignError(Exception):
    pass


class CampaignNotFoundError(CampaignError):
    pass


class CampaignConflictError(CampaignError):
    pass


async def create_campaign(
    db: AsyncSession, user_id: uuid.UUID, data: CampaignCreate
) -> Campaign:
    campaign = Campaign(user_id=user_id, **data.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def list_campaigns(db: AsyncSession, user_id: uuid.UUID) -> list[Campaign]:
    result = await db.scalars(select(Campaign).where(Campaign.user_id == user_id))
    return list(result.all())


async def get_campaign(
    db: AsyncSession, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = await db.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.user_id == user_id
        )
    )
    if not campaign:
        raise CampaignNotFoundError("Campaign not found")
    return campaign


async def update_campaign(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
) -> Campaign:
    campaign = await get_campaign(db, user_id, campaign_id)
    if campaign.status != CampaignStatus.draft:
        raise CampaignConflictError("Only draft campaigns can be updated")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def delete_campaign(
    db: AsyncSession, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> None:
    campaign = await get_campaign(db, user_id, campaign_id)
    if campaign.status not in (CampaignStatus.draft, CampaignStatus.cancelled):
        raise CampaignConflictError("Only draft or cancelled campaigns can be deleted")
    await db.delete(campaign)
    await db.commit()


async def list_campaign_recipients(
    db: AsyncSession, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> list[Recipient]:
    await get_campaign(db, user_id, campaign_id)  # ownership check
    rows = await db.scalars(
        select(Recipient)
        .join(CampaignRecipient, CampaignRecipient.recipient_id == Recipient.id)
        .where(CampaignRecipient.campaign_id == campaign_id)
    )
    return list(rows.all())


async def add_recipient_to_campaign(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
    recipient_id: uuid.UUID,
) -> None:
    await get_campaign(db, user_id, campaign_id)  # ownership check
    # Verify recipient belongs to this user
    recipient = await db.scalar(
        select(Recipient).where(
            Recipient.id == recipient_id, Recipient.user_id == user_id
        )
    )
    if not recipient:
        raise CampaignNotFoundError("Recipient not found")
    link = CampaignRecipient(campaign_id=campaign_id, recipient_id=recipient_id)
    db.add(link)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise CampaignConflictError("Recipient is already added to this campaign")


async def remove_recipient_from_campaign(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
    recipient_id: uuid.UUID,
) -> None:
    await get_campaign(db, user_id, campaign_id)  # ownership check
    link = await db.scalar(
        select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.recipient_id == recipient_id,
        )
    )
    if not link:
        raise CampaignNotFoundError("Recipient is not part of this campaign")
    await db.delete(link)
    await db.commit()
