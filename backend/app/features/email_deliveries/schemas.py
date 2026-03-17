import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.domain.enums import DeliveryStatus


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    recipient_id: uuid.UUID
    status: DeliveryStatus
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class DeliveryStatsResponse(BaseModel):
    total: int
    sent: int
    opened: int
    clicked: int
    bounced: int
    failed: int


class CsvDeliveryTaskResponse(BaseModel):
    task_id: str
    status: str
