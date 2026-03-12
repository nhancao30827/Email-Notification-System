import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.domain.enums import RecipientStatus


class RecipientCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class RecipientUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[RecipientStatus] = None


class RecipientResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: Optional[str]
    status: RecipientStatus
    created_at: datetime

    model_config = {"from_attributes": True}
