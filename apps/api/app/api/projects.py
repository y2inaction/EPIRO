"""Project endpoints, with their milestones and indicators.

Milestones and indicators are exposed beneath a project rather than as
top-level resources because neither means anything without one.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.authorization import PROGRAMME_MANAGERS, PROJECT_EDITORS, AccessControl, get_access
from app.database import get_db
from app.models import (
    Evidence,
    Geography,
    Indicator,
    Milestone,
    Programme,
    Project,
    ProjectStatus,
)
from app.repositories.base import BaseRepository
from app.schemas.core import (
    IndicatorCreate,
    IndicatorResponse,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectStatusChange,
    ProjectUpdate,
)
from app.services.geography import descendant_ids
from app.services.project import apply_status_change

router = APIRouter()

STATUS_CHANGED = "status_changed"


def _get_scoped_project(db: Session, project_id: uuid.UUID, access: AccessControl) -> Project:
    """Load a project the caller is entitled to see."""
    project = db.get(Project, project_id)
    if project is None or not access.can_access(project.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def _check_references(db: Session, organisation_id: uuid.UUID, payload: dict) -> None:
    """Reject references that point outside the project's organisation."""
    programme_id = payload.get("programme_id")
    if programme_id is not None:
        programme = db.get(Programme, programme_id)
        if programme is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Programme not found",
            )
        if programme.organisation_id != organisation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Programme belongs to a different organisation",
            )

    geography_id = payload.get("geography_id")
    if geography_id is not None and db.get(Geography, geography_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geographic area not found",
        )


@router.get("/", response_model=dict)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    organisation_id: Optional[uuid.UUID] = Query(None),
    programme_id: Optional[uuid.UUID] = Query(None),
    project_status: Optional[ProjectStatus] = Query(None),
    geography_id: Optional[uuid.UUID] = Query(
        None, description="Includes projects in any area beneath this one"
    ),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List projects within the caller's organisations."""
    query = db.query(Project)

    if organisation_id:
        access.require_member(organisation_id)
        query = query.filter(Project.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(Project.organisation_id.in_(access.organisation_ids))

    if programme_id is not None:
        query = query.filter(Project.programme_id == programme_id)
    if project_status is not None:
        query = query.filter(Project.status == project_status)
    if geography_id is not None:
        # Filtering by a state should return everything in its LGAs too,
        # otherwise the hierarchy is decorative.
        query = query.filter(Project.geography_id.in_(descendant_ids(db, geography_id)))

    total = query.count()
    projects = query.order_by(Project.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [ProjectResponse.model_validate(item) for item in projects],
    }


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get one project."""
    return _get_scoped_project(db, project_id, access)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: Request,
    project_create: ProjectCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Create a project. It starts as proposed."""
    access.require_role(project_create.organisation_id, PROJECT_EDITORS)

    project_data = project_create.model_dump()
    _check_references(db, project_create.organisation_id, project_data)

    repo = BaseRepository(db, Project)
    if repo.exists(organisation_id=project_create.organisation_id, code=project_create.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A project with that code already exists in this organisation",
        )

    project_data["created_by"] = access.user.id
    project = repo.create(project_data)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="project",
        entity_id=project.id,
        user=access.user,
        organisation_id=project.organisation_id,
        new_values={"code": project.code, "name": project.name},
        request=request,
    )
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    request: Request,
    project_id: uuid.UUID,
    project_update: ProjectUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update a project's details."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROJECT_EDITORS)
    organisation_id = project.organisation_id

    update_data = project_update.model_dump(exclude_unset=True)
    _check_references(db, organisation_id, update_data)

    update_data["updated_by"] = access.user.id
    old_values = {field: audit.serialise(getattr(project, field, None)) for field in update_data}

    updated = BaseRepository(db, Project).update(project_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="project",
        entity_id=project_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.post("/{project_id}/status", response_model=ProjectResponse)
async def change_project_status(
    request: Request,
    project_id: uuid.UUID,
    change: ProjectStatusChange,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Move a project through its lifecycle."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROGRAMME_MANAGERS)

    previous = project.status.value
    apply_status_change(project, change.status, change.actual_completion)
    project.updated_by = access.user.id

    db.commit()
    db.refresh(project)

    audit.record(
        db,
        action=STATUS_CHANGED,
        entity_type="project",
        entity_id=project_id,
        user=access.user,
        organisation_id=project.organisation_id,
        old_values={"status": previous},
        new_values={
            "status": change.status.value,
            "actual_completion": audit.serialise(project.actual_completion),
            "note": change.note,
        },
        request=request,
    )
    return project


@router.delete("/{project_id}")
async def delete_project(
    request: Request,
    project_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete a project that no evidence cites."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROGRAMME_MANAGERS)

    in_use = db.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.project_id == project_id)
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete a project cited by {in_use} evidence records. "
                "Archive it instead so the record of what was done survives."
            ),
        )

    removed = {"code": project.code, "name": project.name, "status": project.status.value}
    organisation_id = project.organisation_id

    db.delete(project)
    db.commit()

    audit.record(
        db,
        action=audit.DELETED,
        entity_type="project",
        entity_id=project_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=removed,
        request=request,
    )
    return {"message": "Project deleted successfully"}


# --- Milestones ------------------------------------------------------------


@router.get("/{project_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(
    project_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List a project's milestones in sequence."""
    _get_scoped_project(db, project_id, access)

    milestones = (
        db.query(Milestone)
        .filter(Milestone.project_id == project_id)
        .order_by(Milestone.sequence, Milestone.due_date)
        .all()
    )
    return [MilestoneResponse.model_validate(item) for item in milestones]


@router.post(
    "/{project_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    request: Request,
    project_id: uuid.UUID,
    milestone_create: MilestoneCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Add a milestone to a project."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROJECT_EDITORS)

    milestone = Milestone(
        project_id=project_id,
        created_by=access.user.id,
        **milestone_create.model_dump(),
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="milestone",
        entity_id=milestone.id,
        user=access.user,
        organisation_id=project.organisation_id,
        new_values={"title": milestone.title, "project_id": str(project_id)},
        request=request,
    )
    return milestone


@router.put("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    request: Request,
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    milestone_update: MilestoneUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update a milestone."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROJECT_EDITORS)

    milestone = db.get(Milestone, milestone_id)
    if milestone is None or milestone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )

    update_data = milestone_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id
    old_values = {field: audit.serialise(getattr(milestone, field, None)) for field in update_data}

    updated = BaseRepository(db, Milestone).update(milestone_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="milestone",
        entity_id=milestone_id,
        user=access.user,
        organisation_id=project.organisation_id,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.delete("/{project_id}/milestones/{milestone_id}")
async def delete_milestone(
    request: Request,
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete a milestone."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROJECT_EDITORS)

    milestone = db.get(Milestone, milestone_id)
    if milestone is None or milestone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )

    removed = {"title": milestone.title, "status": milestone.status.value}
    db.delete(milestone)
    db.commit()

    audit.record(
        db,
        action=audit.DELETED,
        entity_type="milestone",
        entity_id=milestone_id,
        user=access.user,
        organisation_id=project.organisation_id,
        old_values=removed,
        request=request,
    )
    return {"message": "Milestone deleted successfully"}


# --- Indicators ------------------------------------------------------------


@router.get("/{project_id}/indicators", response_model=list[IndicatorResponse])
async def list_indicators(
    project_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List a project's indicators."""
    _get_scoped_project(db, project_id, access)

    indicators = (
        db.query(Indicator)
        .filter(Indicator.project_id == project_id)
        .order_by(Indicator.name)
        .all()
    )
    return [IndicatorResponse.model_validate(item) for item in indicators]


@router.post(
    "/{project_id}/indicators",
    response_model=IndicatorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_indicator(
    request: Request,
    project_id: uuid.UUID,
    indicator_create: IndicatorCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Add an indicator to a project."""
    project = _get_scoped_project(db, project_id, access)
    access.require_role(project.organisation_id, PROJECT_EDITORS)

    if indicator_create.organisation_id != project.organisation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Indicator belongs to a different organisation from its project",
        )

    payload = indicator_create.model_dump()
    payload["project_id"] = project_id
    payload["created_by"] = access.user.id

    indicator = BaseRepository(db, Indicator).create(payload)
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="indicator",
        entity_id=indicator.id,
        user=access.user,
        organisation_id=project.organisation_id,
        new_values={"name": indicator.name, "project_id": str(project_id)},
        request=request,
    )
    return indicator
