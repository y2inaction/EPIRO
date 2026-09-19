"""Organisation management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.authorization import ORG_ADMINS, AccessControl, get_access
from app.database import get_db
from app.models import Organisation
from app.repositories.base import BaseRepository
from app.schemas.core import OrganisationCreate, OrganisationResponse, OrganisationUpdate

router = APIRouter()


def _get_scoped_organisation(
    db: Session, organisation_id: uuid.UUID, access: AccessControl
) -> Organisation:
    """Load an organisation the caller belongs to."""
    org = BaseRepository(db, Organisation).get_by_id(organisation_id)
    if not org or not access.can_access(organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )
    return org


@router.get("/", response_model=dict)
async def list_organisations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List the organisations the caller belongs to."""
    query = db.query(Organisation)
    if not access.is_platform_admin:
        query = query.filter(Organisation.id.in_(access.organisation_ids))

    total = query.count()
    orgs = query.offset(skip).limit(limit).all()

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
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get organisation by ID."""
    return _get_scoped_organisation(db, organisation_id, access)


@router.post("/", response_model=OrganisationResponse, status_code=status.HTTP_201_CREATED)
async def create_organisation(
    org_create: OrganisationCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Create a new organisation."""
    access.require_platform_admin()

    org_repo = BaseRepository(db, Organisation)
    if org_repo.exists(code=org_create.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organisation code already exists",
        )

    org_data = org_create.model_dump()
    org_data["created_by"] = access.user.id

    return org_repo.create(org_data)


@router.put("/{organisation_id}", response_model=OrganisationResponse)
async def update_organisation(
    organisation_id: uuid.UUID,
    org_update: OrganisationUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update organisation."""
    _get_scoped_organisation(db, organisation_id, access)
    access.require_role(organisation_id, ORG_ADMINS)

    update_data = org_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id

    return BaseRepository(db, Organisation).update(organisation_id, update_data)


@router.delete("/{organisation_id}")
async def delete_organisation(
    organisation_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete an organisation and everything it owns."""
    access.require_platform_admin()

    org_repo = BaseRepository(db, Organisation)
    if not org_repo.delete(organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    return {"message": "Organisation deleted successfully"}
