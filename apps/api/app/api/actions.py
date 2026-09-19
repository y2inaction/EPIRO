"""The decision register (the last link in the intelligence chain).

Evidence becomes a signal, a signal is assessed into a finding, the finding
implies something for readiness, and that implication becomes an action
somebody owns. Everything up to the finding was already built; this is what
turns knowing into deciding.

The rules live in ``app.services.actions``. Three are worth restating:

**An action cites what prompted it**, and the cited record is checked to exist
inside the caller's organisations. A register nobody can trace back to a
finding is a wish list.

**Closing requires a written outcome.** The status is not the interesting
part; what happened is.

**Deciding not to act is recorded, not deleted.** ``dropped`` keeps the
decision and its reasoning, which is usually the part worth having.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.audit import ACCEPTED, CANCELLED, COMPLETED, CREATED, STARTED, UPDATED, record
from app.authorization import ACTION_OWNERS, AccessControl, get_access
from app.database import get_db
from app.models import Action, ActionOrigin, ActionStatus
from app.schemas.core import (
    ActionCreate,
    ActionOutcome,
    ActionResponse,
    ActionUpdate,
)
from app.services import actions as rules

router = APIRouter()

ENTITY = "action"


def _serialise(action: Action) -> ActionResponse:
    """An action, with overdue derived rather than read from a column."""
    response = ActionResponse.model_validate(action)
    response.overdue = rules.is_overdue(action)
    return response


def _scoped(db: Session, action_id: uuid.UUID, access: AccessControl) -> Action:
    """Fetch an action the caller may see, or refuse."""
    action = db.query(Action).filter(Action.id == action_id).first()

    if action is None or (
        not access.is_platform_admin and action.organisation_id not in access.organisation_ids
    ):
        # Same answer for "does not exist" and "not yours", so the register
        # cannot be probed for which identifiers are real elsewhere.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")

    return action


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def raise_action(
    request: Request,
    payload: ActionCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Raise an action against something the organisation already holds."""
    access.require_role(payload.organisation_id, ACTION_OWNERS)
    rules.require_origin(
        db,
        payload.origin_type,
        payload.origin_id,
        sorted(access.organisation_ids),
        access.is_platform_admin,
    )

    action = Action(
        **payload.model_dump(),
        status=ActionStatus.PROPOSED,
        created_by_id=access.user.id,
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    record(
        db,
        action=CREATED,
        entity_type=ENTITY,
        entity_id=action.id,
        user=access.user,
        organisation_id=action.organisation_id,
        new_values={
            "title": action.title,
            "status": action.status.value,
            "origin_type": action.origin_type.value,
            "origin_id": str(action.origin_id),
            "owner_id": str(action.owner_id),
        },
        request=request,
    )
    return _serialise(action)


@router.get("/", response_model=dict)
async def list_actions(
    organisation_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[ActionStatus] = Query(None, alias="status"),
    origin_type: Optional[ActionOrigin] = Query(None),
    origin_id: Optional[uuid.UUID] = Query(None),
    scenario_id: Optional[uuid.UUID] = Query(None),
    overdue: Optional[bool] = Query(None, description="Only actions past their date"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """The register, narrowed.

    There is deliberately no filter by owner. Who owns an action is on the
    action, where it is accountability; a register that can be sliced by
    person is a report on staff, and spec section 4's prohibition on
    profiling is not only about citizens.
    """
    query = db.query(Action)

    if not access.is_platform_admin:
        query = query.filter(Action.organisation_id.in_(access.organisation_ids))
    if organisation_id is not None:
        query = query.filter(Action.organisation_id == organisation_id)
    if status_filter is not None:
        query = query.filter(Action.status == status_filter)
    if origin_type is not None:
        query = query.filter(Action.origin_type == origin_type)
    if origin_id is not None:
        query = query.filter(Action.origin_id == origin_id)
    if scenario_id is not None:
        query = query.filter(Action.scenario_id == scenario_id)

    rows = query.order_by(Action.created_at.desc()).all()

    if overdue is not None:
        # Filtered in Python because overdue is derived, not stored. The
        # register is small enough per organisation that this is honest
        # rather than clever.
        rows = [row for row in rows if rules.is_overdue(row) == overdue]

    total = len(rows)
    page = rows[skip : skip + limit]

    result: Dict[str, Any] = {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [_serialise(row) for row in page],
    }
    return result


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """One action."""
    return _serialise(_scoped(db, action_id, access))


@router.patch("/{action_id}", response_model=ActionResponse)
async def revise_action(
    request: Request,
    action_id: uuid.UUID,
    payload: ActionUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Revise an action that is still open."""
    action = _scoped(db, action_id, access)
    access.require_role(action.organisation_id, ACTION_OWNERS)
    rules.require_open(action)

    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(action, field) for field in changes}

    for field, value in changes.items():
        setattr(action, field, value)
    db.commit()
    db.refresh(action)

    record(
        db,
        action=UPDATED,
        entity_type=ENTITY,
        entity_id=action.id,
        user=access.user,
        organisation_id=action.organisation_id,
        old_values={k: str(v) if v is not None else None for k, v in before.items()},
        new_values={k: str(v) if v is not None else None for k, v in changes.items()},
        request=request,
    )
    return _serialise(action)


def _move(
    request: Request,
    db: Session,
    access: AccessControl,
    action: Action,
    to: ActionStatus,
    entry: str,
    outcome: Optional[str] = None,
) -> ActionResponse:
    """Move an action along its lifecycle, recording what changed."""
    access.require_role(action.organisation_id, ACTION_OWNERS)
    rules.require_transition(action, to)

    was = action.status.value
    action.status = to

    if to is ActionStatus.IN_PROGRESS:
        action.started_at = datetime.now(timezone.utc)
    if to in rules.CLOSED:
        action.outcome = rules.require_outcome(outcome)
        action.closed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(action)

    record(
        db,
        action=entry,
        entity_type=ENTITY,
        entity_id=action.id,
        user=access.user,
        organisation_id=action.organisation_id,
        old_values={"status": was},
        new_values={"status": action.status.value},
        request=request,
    )
    return _serialise(action)


@router.post("/{action_id}/accept", response_model=ActionResponse)
async def accept_action(
    request: Request,
    action_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Agree that this will be done."""
    action = _scoped(db, action_id, access)
    return _move(request, db, access, action, ActionStatus.ACCEPTED, ACCEPTED)


@router.post("/{action_id}/start", response_model=ActionResponse)
async def start_action(
    request: Request,
    action_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Begin work on it."""
    action = _scoped(db, action_id, access)
    return _move(request, db, access, action, ActionStatus.IN_PROGRESS, STARTED)


@router.post("/{action_id}/complete", response_model=ActionResponse)
async def complete_action(
    request: Request,
    action_id: uuid.UUID,
    payload: ActionOutcome,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Record that it was carried out, and what happened."""
    action = _scoped(db, action_id, access)
    return _move(request, db, access, action, ActionStatus.DONE, COMPLETED, payload.outcome)


@router.post("/{action_id}/drop", response_model=ActionResponse)
async def drop_action(
    request: Request,
    action_id: uuid.UUID,
    payload: ActionOutcome,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Record a decision not to do it, and why.

    Kept rather than deleted. The reason for not acting is usually the part
    worth having when somebody asks later why nothing happened.
    """
    action = _scoped(db, action_id, access)
    return _move(request, db, access, action, ActionStatus.DROPPED, CANCELLED, payload.outcome)


@router.get("/origin/{origin_type}/{origin_id}", response_model=List[ActionResponse])
async def actions_from(
    origin_type: ActionOrigin,
    origin_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """What was decided because of this finding.

    The chain read in the other direction. A finding with no actions against
    it is a thing the organisation knows and has not acted on, which is worth
    being able to see from the finding itself.
    """
    query = db.query(Action).filter(
        Action.origin_type == origin_type, Action.origin_id == origin_id
    )
    if not access.is_platform_admin:
        query = query.filter(Action.organisation_id.in_(access.organisation_ids))

    return [_serialise(row) for row in query.order_by(Action.created_at.desc()).all()]
