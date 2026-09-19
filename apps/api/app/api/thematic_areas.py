"""Thematic stream endpoints.

The eight streams in spec section 9 are shared reference data, like the
administrative map: every organisation files evidence against the same
taxonomy so that work can be compared across them. Reads are open to any
authenticated user, writes are platform-administrator only.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.authorization import AccessControl, get_access
from app.database import get_db
from app.models import Evidence, ThematicArea
from app.repositories.base import BaseRepository
from app.schemas.core import ThematicAreaCreate, ThematicAreaResponse, ThematicAreaUpdate

router = APIRouter()


def _get_area(db: Session, area_id: uuid.UUID) -> ThematicArea:
    """Load a thematic area or report it missing."""
    area = db.get(ThematicArea, area_id)
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thematic area not found",
        )
    return area


@router.get("/", response_model=dict)
async def list_thematic_areas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_inactive: bool = Query(False),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List the thematic streams."""
    query = db.query(ThematicArea)

    if not include_inactive:
        query = query.filter(ThematicArea.is_active.is_(True))
    if search:
        query = query.filter(ThematicArea.name.ilike(f"{search}%"))

    total = query.count()
    areas = query.order_by(ThematicArea.order, ThematicArea.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [ThematicAreaResponse.model_validate(area) for area in areas],
    }


@router.get("/{area_id}", response_model=ThematicAreaResponse)
async def get_thematic_area(
    area_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get one thematic stream."""
    return _get_area(db, area_id)


@router.post("/", response_model=ThematicAreaResponse, status_code=status.HTTP_201_CREATED)
async def create_thematic_area(
    request: Request,
    area_create: ThematicAreaCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Add a thematic stream. Platform administrators only."""
    access.require_platform_admin()

    repo = BaseRepository(db, ThematicArea)
    if repo.exists(code=area_create.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A thematic area with that code already exists",
        )

    area_data = area_create.model_dump()
    area_data["created_by"] = access.user.id

    area = repo.create(area_data)
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="thematic_area",
        entity_id=area.id,
        user=access.user,
        new_values={"code": area.code, "name": area.name},
        request=request,
    )
    return area


@router.put("/{area_id}", response_model=ThematicAreaResponse)
async def update_thematic_area(
    request: Request,
    area_id: uuid.UUID,
    area_update: ThematicAreaUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update a thematic stream. Platform administrators only."""
    access.require_platform_admin()
    area = _get_area(db, area_id)

    update_data = area_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id
    old_values = {field: audit.serialise(getattr(area, field, None)) for field in update_data}

    updated = BaseRepository(db, ThematicArea).update(area_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="thematic_area",
        entity_id=area_id,
        user=access.user,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.delete("/{area_id}")
async def delete_thematic_area(
    request: Request,
    area_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete a thematic stream that nothing is filed under.

    A stream in use should be deactivated rather than removed, so existing
    evidence keeps the classification it was filed with.
    """
    access.require_platform_admin()
    area = _get_area(db, area_id)

    in_use = db.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.thematic_area_id == area_id)
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete a thematic area used by {in_use} evidence records. "
                "Deactivate it instead so existing records keep their classification."
            ),
        )

    removed = {"code": area.code, "name": area.name}
    db.delete(area)
    db.commit()

    audit.record(
        db,
        action=audit.DELETED,
        entity_type="thematic_area",
        entity_id=area_id,
        user=access.user,
        old_values=removed,
        request=request,
    )
    return {"message": "Thematic area deleted successfully"}
