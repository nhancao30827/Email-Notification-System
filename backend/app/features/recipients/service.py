import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.recipients.schemas import RecipientCreate, RecipientUpdate
from app.infrastructure.database.models.recipient import Recipient


class RecipientError(Exception):
    pass


class RecipientNotFoundError(RecipientError):
    pass


class RecipientConflictError(RecipientError):
    pass


async def create_recipient(
    db: AsyncSession, user_id: uuid.UUID, data: RecipientCreate
) -> Recipient:
    recipient = Recipient(user_id=user_id, **data.model_dump())
    db.add(recipient)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise RecipientConflictError("Recipient with this email already exists")
    await db.refresh(recipient)
    return recipient


async def list_recipients(db: AsyncSession, user_id: uuid.UUID) -> list[Recipient]:
    result = await db.scalars(select(Recipient).where(Recipient.user_id == user_id))
    return list(result.all())


async def get_recipient(
    db: AsyncSession, user_id: uuid.UUID, recipient_id: uuid.UUID
) -> Recipient:
    recipient = await db.scalar(
        select(Recipient).where(
            Recipient.id == recipient_id, Recipient.user_id == user_id
        )
    )
    if not recipient:
        raise RecipientNotFoundError("Recipient not found")
    return recipient


async def update_recipient(
    db: AsyncSession,
    user_id: uuid.UUID,
    recipient_id: uuid.UUID,
    data: RecipientUpdate,
) -> Recipient:
    recipient = await get_recipient(db, user_id, recipient_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(recipient, field, value)
    await db.commit()
    await db.refresh(recipient)
    return recipient


async def delete_recipient(
    db: AsyncSession, user_id: uuid.UUID, recipient_id: uuid.UUID
) -> None:
    recipient = await get_recipient(db, user_id, recipient_id)
    await db.delete(recipient)
    await db.commit()
