import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.features.recipients import service
from app.features.recipients.schemas import RecipientCreate, RecipientResponse, RecipientUpdate
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/recipients", tags=["recipients"])


@router.post("", response_model=RecipientResponse, status_code=status.HTTP_201_CREATED)
async def create_recipient(
    data: RecipientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a recipient record for the authenticated user."""
    try:
        return await service.create_recipient(db, current_user.id, data)
    except service.RecipientConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[RecipientResponse])
async def list_recipients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all recipients owned by the current user."""
    return await service.list_recipients(db, current_user.id)


@router.get("/{recipient_id}", response_model=RecipientResponse)
async def get_recipient(
    recipient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one recipient by id for the current user."""
    try:
        return await service.get_recipient(db, current_user.id, recipient_id)
    except service.RecipientNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{recipient_id}", response_model=RecipientResponse)
async def update_recipient(
    recipient_id: uuid.UUID,
    data: RecipientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update recipient fields for a user-owned recipient."""
    try:
        return await service.update_recipient(db, current_user.id, recipient_id, data)
    except service.RecipientNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipient(
    recipient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a recipient owned by the authenticated user."""
    try:
        await service.delete_recipient(db, current_user.id, recipient_id)
    except service.RecipientNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
