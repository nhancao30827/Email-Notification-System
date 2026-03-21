import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.campaign import Campaign
    from app.infrastructure.database.models.recipient import Recipient


class CampaignRecipient(Base):
    """Association table between Campaign and Recipient (composite PK)."""

    __tablename__ = "campaign_recipients"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipients.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        back_populates="campaign_recipients", lazy="selectin"
    )
    recipient: Mapped["Recipient"] = relationship(
        back_populates="campaign_recipients", lazy="selectin"
    )
