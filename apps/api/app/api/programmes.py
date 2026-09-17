"""Programme endpoints.

A programme groups projects under one intent. Spec section 12 treats it as the
level above a project, so evidence can roll up from project to programme to
thematic stream.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.authorization import PROGRAMME_MANAGERS, AccessControl, get_access
from app.database import get_db
from app.models import Programme, Project
from app.repositories.base import BaseRepository
from app.schemas.core import ProgrammeCreate, ProgrammeResponse, ProgrammeUpdate

router = APIRouter()


def _get_scoped_programme(db: Session, programme_id: uuid.UUID, access: AccessControl) -> Programme:
    """Load a programme the caller is entitled to see."""
    programme = db.get(Programme, programme_id)
    if programme is None or not access.can_access(programme.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme not found",
        )
    return programme


@router.get("/", response_model=dict)
async def list_programmes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    organisation_id: Optional[uuid.UUID] = Query(None),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List programmes within the caller's organisations."""
    query = db.query(Programme)

    if organisation_id:
        access.require_member(organisation_id)
        query = query.filter(Programme.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(Programme.organisation_id.in_(access.organisation_ids))

    total = query.count()
    programmes = query.order_by(Programme.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [ProgrammeResponse.model_validate(item) for item in programmes],
    }


@router.get("/{programme_id}", response_model=ProgrammeResponse)
async def get_programme(
    programme_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get one programme."""
    return _get_scoped_programme(db, programme_id, access)


@router.post("/", response_model=ProgrammeResponse, status_code=status.HTTP_201_CREATED)
async def create_programme(
    request: Request,
    programme_create: ProgrammeCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Create a programme."""
    access.require_role(programme_create.organisation_id, PROGRAMME_MANAGERS)

    repo = BaseRepository(db, Programme)
    if repo.exists(organisation_id=programme_create.organisation_id, code=programme_create.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A programme with that code already exists in this organisation",
        )

    programme_data = programme_create.model_dump()
    programme_data["created_by"] = access.user.id

    programme = repo.create(programme_data)
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="programme",
        entity_id=programme.id,
        user=access.user,
        organisation_id=programme.organisation_id,
        new_values={"code": programme.code, "name": programme.name},
        request=request,
    )
    return programme


@router.put("/{programme_id}", response_model=ProgrammeResponse)
async def update_programme(
    request: Request,
    programme_id: uuid.UUID,
    programme_update: ProgrammeUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update a programme."""
    programme = _get_scoped_programme(db, programme_id, access)
    access.require_role(programme.organisation_id, PROGRAMME_MANAGERS)
    organisation_id = programme.organisation_id

    update_data = programme_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id
    old_values = {field: audit.serialise(getattr(programme, field, None)) for field in update_data}

    updated = BaseRepository(db, Programme).update(programme_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="programme",
        entity_id=programme_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.delete("/{programme_id}")
async def delete_programme(
    request: Request,
    programme_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete a programme that holds no projects."""
    programme = _get_scoped_programme(db, programme_id, access)
    access.require_role(programme.organisation_id, PROGRAMME_MANAGERS)

    project_count = db.scalar(
        select(func.count()).select_from(Project).where(Project.programme_id == programme_id)
    )
    if project_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete a programme holding {project_count} projects. "
                "Move or archive them first."
            ),
        )

    removed = {"code": programme.code, "name": programme.name}
    organisation_id = programme.organisation_id

    db.delete(programme)
    db.commit()

    audit.record(
        db,
        action=audit.DELETED,
        entity_type="programme",
        entity_id=programme_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=removed,
        request=request,
    )
    return {"message": "Programme deleted successfully"}
