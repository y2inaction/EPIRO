"""Organisation management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin_user, get_current_user
from app.models import Organisation, User
from app.repositories.base import BaseRepository
from app.schemas.core import OrganisationCreate, OrganisationResponse, OrganisationUpdate

router = APIRouter()


@router.get("/", response_model=dict)
async def list_organisations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all organisations."""
    org_repo = BaseRepository(db, Organisation)
    orgs, total = org_repo.get_all(skip, limit)

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [OrganisationResponse.model_validate(org) for org in orgs],
    }


@router.get("/{organisation_id}", response_model=OrganisationResponse)
async def get_organisation(
    organisation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get organisation by ID."""
    org_repo = BaseRepository(db, Organisation)
    org = org_repo.get_by_id(organisation_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    return org


@router.post("/", response_model=OrganisationResponse)
async def create_organisation(
    org_create: OrganisationCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Create a new organisation."""
    org_repo = BaseRepository(db, Organisation)

    # Check if organisation code already exists
    if org_repo.exists(code=org_create.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organisation code already exists",
        )

    org_data = org_create.model_dump()
    org_data["created_by"] = current_user.id

    org = org_repo.create(org_data)
    return org


@router.put("/{organisation_id}", response_model=OrganisationResponse)
async def update_organisation(
    organisation_id: uuid.UUID,
    org_update: OrganisationUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Update organisation."""
    org_repo = BaseRepository(db, Organisation)
    org = org_repo.get_by_id(organisation_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    update_data = org_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = current_user.id
    updated_org = org_repo.update(organisation_id, update_data)

    return updated_org


@router.delete("/{organisation_id}")
async def delete_organisation(
    organisation_id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Delete organisation."""
    org_repo = BaseRepository(db, Organisation)

    if not org_repo.delete(organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    return {"message": "Organisation deleted successfully"}
