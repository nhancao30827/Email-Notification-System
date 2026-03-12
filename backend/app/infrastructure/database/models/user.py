import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.campaign import Campaign
    from app.infrastructure.database.models.recipient import Recipient


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )
    recipients: Mapped[list["Recipient"]] = relationship(
        back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )
