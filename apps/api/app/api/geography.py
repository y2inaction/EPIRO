"""Administrative geography endpoints.

The hierarchy is reference data shared by every organisation, so reads are open
to any authenticated user while writes are restricted to platform
administrators. Scoping it per tenant would make cross-tenant comparison
impossible and duplicate the same national map many times over.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.authorization import AccessControl, get_access
from app.database import get_db
from app.models import Evidence, Geography, GeographyLevel, Location, Project, Question
from app.schemas.core import GeographyCreate, GeographyResponse, GeographyUpdate
from app.services.geography import ancestors, resolve_parent

router = APIRouter()


def _get_area(db: Session, area_id: uuid.UUID) -> Geography:
    """Load an area or report it missing."""
    area = db.get(Geography, area_id)
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geographic area not found",
        )
    return area


def _point_wkt(latitude: Optional[object], longitude: Optional[object]) -> Optional[str]:
    """Build a PostGIS point literal, or None when either value is absent."""
    if latitude is None or longitude is None:
        return None
    return f"SRID=4326;POINT({longitude} {latitude})"


@router.get("/", response_model=dict)
async def list_areas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    level: Optional[GeographyLevel] = Query(None),
    parent_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None, min_length=1, max_length=160),
    include_inactive: bool = Query(False),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List areas, optionally filtered by level, parent or name."""
    query = db.query(Geography)

    if level is not None:
        query = query.filter(Geography.level == level)
    if parent_id is not None:
        query = query.filter(Geography.parent_id == parent_id)
    if search:
        query = query.filter(Geography.name.ilike(f"{search}%"))
    if not include_inactive:
        query = query.filter(Geography.is_active.is_(True))

    total = query.count()
    areas = query.order_by(Geography.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [GeographyResponse.model_validate(area) for area in areas],
    }


@router.get("/{area_id}", response_model=GeographyResponse)
async def get_area(
    area_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get one area."""
    return _get_area(db, area_id)


@router.get("/{area_id}/children", response_model=list[GeographyResponse])
async def list_children(
    area_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List the areas directly beneath one area."""
    _get_area(db, area_id)

    children = (
        db.query(Geography).filter(Geography.parent_id == area_id).order_by(Geography.name).all()
    )
    return [GeographyResponse.model_validate(child) for child in children]


@router.get("/{area_id}/ancestors", response_model=list[GeographyResponse])
async def list_ancestors(
    area_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List the chain from an area up to its country, nearest parent first."""
    _get_area(db, area_id)
    return [GeographyResponse.model_validate(node) for node in ancestors(db, area_id)]


@router.post("/", response_model=GeographyResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    request: Request,
    area_create: GeographyCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Create an area. Platform administrators only."""
    access.require_platform_admin()
    resolve_parent(db, area_create.level, area_create.parent_id)

    payload = area_create.model_dump(exclude={"latitude", "longitude"})
    area = Geography(
        **payload,
        centroid=_point_wkt(area_create.latitude, area_create.longitude),
        created_by=access.user.id,
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="geographic_area",
        entity_id=area.id,
        user=access.user,
        new_values={"name": area.name, "level": area.level.value},
        request=request,
    )
    return area


@router.put("/{area_id}", response_model=GeographyResponse)
async def update_area(
    request: Request,
    area_id: uuid.UUID,
    area_update: GeographyUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update an area. Platform administrators only."""
    access.require_platform_admin()
    area = _get_area(db, area_id)

    update_data = area_update.model_dump(exclude_unset=True)
    latitude = update_data.pop("latitude", None)
    longitude = update_data.pop("longitude", None)
    old_values = {field: audit.serialise(getattr(area, field, None)) for field in update_data}

    for field, value in update_data.items():
        setattr(area, field, value)

    point = _point_wkt(latitude, longitude)
    if point is not None:
        area.centroid = point

    area.updated_by = access.user.id
    db.commit()
    db.refresh(area)

    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="geographic_area",
        entity_id=area_id,
        user=access.user,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return area


@router.delete("/{area_id}")
async def delete_area(
    request: Request,
    area_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete an area, provided nothing depends on it."""
    access.require_platform_admin()
    area = _get_area(db, area_id)

    child_count = db.scalar(
        select(func.count()).select_from(Geography).where(Geography.parent_id == area_id)
    )
    if child_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete an area with {child_count} areas beneath it",
        )

    # Deleting an area still referenced would orphan the records that place
    # themselves in it, and the reference is how they are found on a map.
    for model, label in (
        (Project, "projects"),
        (Location, "locations"),
        (Evidence, "evidence records"),
        (Question, "questions"),
    ):
        in_use = db.scalar(
            select(func.count()).select_from(model).where(model.geography_id == area_id)
        )
        if in_use:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete an area still referenced by {in_use} {label}",
            )

    removed = {"name": area.name, "level": area.level.value}
    db.delete(area)
    db.commit()

    audit.record(
        db,
        action=audit.DELETED,
        entity_type="geographic_area",
        entity_id=area_id,
        user=access.user,
        old_values=removed,
        request=request,
    )
    return {"message": "Geographic area deleted successfully"}
