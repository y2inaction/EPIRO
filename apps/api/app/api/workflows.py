"""Workflow definition endpoints (spec section 36).

An organisation defines the review stages its content must clear. What it
cannot define is the lifecycle around them, or a workflow with no separation
of duties — see app/services/workflow.py for why both limits exist.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
from app.authorization import ORG_ADMINS, AccessControl, get_access
from app.database import get_db
from app.models import WorkflowDefinition, WorkflowStage
from app.schemas.core import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionResponse,
)
from app.services import workflow

router = APIRouter()


def _get_scoped_definition(
    db: Session, definition_id: uuid.UUID, access: AccessControl
) -> WorkflowDefinition:
    """Load a definition the caller is entitled to see."""
    definition = db.get(WorkflowDefinition, definition_id)
    if definition is None or not access.can_access(definition.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    return definition


@router.get("/", response_model=List[WorkflowDefinitionResponse])
async def list_workflows(
    organisation_id: uuid.UUID = Query(...),
    entity_type: Optional[str] = Query(None),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """The workflows an organisation has defined."""
    access.require_member(organisation_id)

    query = db.query(WorkflowDefinition).filter(
        WorkflowDefinition.organisation_id == organisation_id
    )
    if entity_type:
        query = query.filter(WorkflowDefinition.entity_type == entity_type)

    return [
        WorkflowDefinitionResponse.model_validate(definition)
        for definition in query.order_by(WorkflowDefinition.entity_type).all()
    ]


@router.get("/{definition_id}", response_model=WorkflowDefinitionResponse)
async def get_workflow(
    definition_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """One workflow definition."""
    return _get_scoped_definition(db, definition_id, access)


@router.post("/", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: Request,
    definition_create: WorkflowDefinitionCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Define the review stages for one kind of content.

    Replaces whatever was active for that content type: two active definitions
    would make "which workflow applies" ambiguous, and that question must
    never be ambiguous for an approval. The old one is deactivated rather than
    deleted, so the trail of records that cleared its stages still resolves.
    """
    access.require_role(definition_create.organisation_id, ORG_ADMINS)

    stages = [stage.model_dump() for stage in definition_create.stages]
    workflow.validate_stages(stages)

    existing = workflow.active_definition(
        db, definition_create.organisation_id, definition_create.entity_type
    )
    if existing is not None:
        existing.is_active = False
        existing.updated_by = access.user.id
        db.flush()

    definition = WorkflowDefinition(
        organisation_id=definition_create.organisation_id,
        entity_type=definition_create.entity_type,
        name=definition_create.name,
        description=definition_create.description,
        created_by=access.user.id,
    )
    db.add(definition)
    db.flush()

    for position, stage in enumerate(stages):
        db.add(
            WorkflowStage(
                definition_id=definition.id,
                position=position,
                name=stage["name"],
                required_roles=stage["required_roles"],
                # The final stage always requires a distinct actor, whatever
                # was asked for. validate_stages refuses a definition that
                # says otherwise; this makes the stored row agree.
                requires_distinct_actor=(
                    True if position == len(stages) - 1 else stage["requires_distinct_actor"]
                ),
                created_by=access.user.id,
            )
        )

    db.commit()
    db.refresh(definition)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="workflow_definition",
        entity_id=definition.id,
        user=access.user,
        organisation_id=definition.organisation_id,
        new_values={
            "entity_type": definition.entity_type,
            "name": definition.name,
            "stages": [stage["name"] for stage in stages],
            "replaced": str(existing.id) if existing else None,
        },
        request=request,
    )
    return definition


@router.delete("/{definition_id}")
async def deactivate_workflow(
    request: Request,
    definition_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Stop using a workflow, returning to the single implicit stage.

    Deactivated rather than deleted: records that cleared its stages point at
    them from the approval trail, and a trail that cannot say what was cleared
    is not a trail.
    """
    definition = _get_scoped_definition(db, definition_id, access)
    access.require_role(definition.organisation_id, ORG_ADMINS)
    before = audit.snapshot(definition, "is_active")

    definition.is_active = False
    definition.updated_by = access.user.id
    db.commit()

    audit.record(
        db,
        action=audit.DEACTIVATED,
        entity_type="workflow_definition",
        entity_id=definition_id,
        user=access.user,
        organisation_id=definition.organisation_id,
        old_values=before,
        new_values={"is_active": False},
        request=request,
    )
    return {"message": "Workflow deactivated"}
