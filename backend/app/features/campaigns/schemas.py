import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.domain.enums import CampaignStatus


class CampaignCreate(BaseModel):
    name: str
    subject: str
    body: str


class AddRecipientRequest(BaseModel):
    recipient_id: uuid.UUID


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    subject: str
    body: str
    status: CampaignStatus
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
