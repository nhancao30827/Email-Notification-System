import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import RecipientStatus
from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.campaign_recipient import CampaignRecipient
    from app.infrastructure.database.models.email_delivery import EmailDelivery
    from app.infrastructure.database.models.user import User


class Recipient(Base):
    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_recipients_user_id_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus, name="recipient_status"),
        nullable=False,
        default=RecipientStatus.active,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="recipients", lazy="selectin")
    campaign_recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="recipient", lazy="selectin", cascade="all, delete-orphan"
    )
    email_deliveries: Mapped[list["EmailDelivery"]] = relationship(
        back_populates="recipient", lazy="selectin", cascade="all, delete-orphan"
    )
