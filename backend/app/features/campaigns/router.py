import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.features.campaigns import service
from app.features.campaigns.schemas import AddRecipientRequest, CampaignCreate, CampaignResponse, CampaignUpdate
from app.features.recipients.schemas import RecipientResponse
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a campaign owned by the current user."""
    return await service.create_campaign(db, current_user.id, data)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all campaigns for the authenticated user."""
    return await service.list_campaigns(db, current_user.id)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return one campaign by id for the authenticated user."""
    try:
        return await service.get_campaign(db, current_user.id, campaign_id)
    except service.CampaignNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a draft campaign owned by the authenticated user."""
    try:
        return await service.update_campaign(db, current_user.id, campaign_id, data)
    except service.CampaignNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except service.CampaignConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a campaign if its status allows deletion."""
    try:
        await service.delete_campaign(db, current_user.id, campaign_id)
    except service.CampaignNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except service.CampaignConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{campaign_id}/recipients", response_model=list[RecipientResponse])
async def list_campaign_recipients(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recipients currently linked to a campaign."""
    try:
        return await service.list_campaign_recipients(db, current_user.id, campaign_id)
    except service.CampaignNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{campaign_id}/recipients",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_recipient_to_campaign(
    campaign_id: uuid.UUID,
    data: AddRecipientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach an existing recipient to the campaign."""
    try:
        await service.add_recipient_to_campaign(
            db, current_user.id, campaign_id, data.recipient_id
        )
    except service.CampaignNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except service.CampaignConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete(
    "/{campaign_id}/recipients/{recipient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_recipient_from_campaign(
    campaign_id: uuid.UUID,
    recipient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a recipient association from the campaign."""
    try:
        await service.remove_recipient_from_campaign(
            db, current_user.id, campaign_id, recipient_id
        )
    except service.CampaignNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
