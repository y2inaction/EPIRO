"""Readiness and scenario endpoints (spec sections 28-31).

A scenario is registered, given a playbook, rehearsed, and declared at a
readiness colour that the record has to support. The rule that makes the
colour mean anything lives in ``app.services.readiness``: a status may be
declared as bad as you like and no better than the evidence allows.

Readiness is **not** on the public portal, and that is a decision rather than
an omission. Publishing that a body is RED on flood response tells the public
something true and useful, and tells anyone who would exploit the gap exactly
where it is. Spec section 20 limits collection to legitimate operational
purposes and the same caution applies to disclosure, so the first version
keeps the matrix internal. See docs/READINESS.md.

Nothing here records who failed at anything. A drill finding describes what
the response could not do; spec section 4's prohibition on profiling is not
only about citizens, and a rehearsal is the obvious place a blame column
would otherwise appear.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
from app.authorization import (
    DRILL_CONDUCTORS,
    READINESS_MANAGERS,
    AccessControl,
    get_access,
)
from app.database import get_db
from app.models import (
    Drill,
    DrillFinding,
    DrillStatus,
    Geography,
    Organisation,
    PlaybookStep,
    ReadinessStatus,
    Scenario,
    User,
)
from app.repositories.base import BaseRepository
from app.schemas.core import (
    DrillCancellation,
    DrillCompletion,
    DrillFindingResponse,
    DrillResponse,
    DrillSchedule,
    FindingResolution,
    PlaybookInput,
    ReadinessDeclaration,
    ReadinessFloor,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioUpdate,
)
from app.services import readiness

router = APIRouter()


def _with_floor(scenario: Scenario) -> ScenarioResponse:
    """Serialise a scenario with the floor its record supports.

    Served alongside the declared status on every read, so that nobody has to
    ask a second question to find out whether a colour is backed by anything.
    """
    response = ScenarioResponse.model_validate(scenario)
    floor = readiness.floor_for(scenario)
    response.floor = ReadinessFloor(status=floor.status, reasons=floor.reasons)
    return response


def _scoped_scenario(db: Session, scenario_id: uuid.UUID, access: AccessControl) -> Scenario:
    """Load a scenario the caller's organisations cover."""
    scenario = BaseRepository(db, Scenario).get_by_id(scenario_id)
    if scenario is None or not access.can_access(scenario.organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return scenario


def _scoped_drill(db: Session, drill_id: uuid.UUID, access: AccessControl) -> Drill:
    """Load a drill the caller's organisations cover."""
    drill = BaseRepository(db, Drill).get_by_id(drill_id)
    if drill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drill not found")
    if not access.can_access(drill.scenario.organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drill not found")
    return drill


def _check_references(db: Session, values: dict) -> None:
    """Refuse a reference to something that does not exist."""
    geography_id = values.get("geography_id")
    if geography_id is not None and db.get(Geography, geography_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown area")

    owner = values.get("owner")
    if owner is not None and db.get(User, owner) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user")


@router.get("/", response_model=dict)
async def list_scenarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[ReadinessStatus] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """The readiness matrix for the caller's organisations."""
    query = db.query(Scenario)

    if organisation_id:
        access.require_member(organisation_id)
        query = query.filter(Scenario.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(Scenario.organisation_id.in_(access.organisation_ids))

    if status_filter:
        query = query.filter(Scenario.status == status_filter)

    total = query.count()
    scenarios = query.order_by(Scenario.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [_with_floor(scenario) for scenario in scenarios],
    }


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """One scenario, with its playbook and the floor its record supports."""
    return _with_floor(_scoped_scenario(db, scenario_id, access))


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    request: Request,
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Register something the organisation must be ready for.

    It starts RED. There is no way to create a scenario already declared
    ready, because at creation there is by definition nothing to support it.
    """
    access.require_role(payload.organisation_id, READINESS_MANAGERS)

    organisation = db.get(Organisation, payload.organisation_id)
    if organisation is None or not organisation.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown organisation")

    values = payload.model_dump()
    _check_references(db, values)

    values["created_by"] = access.user.id
    values["updated_by"] = access.user.id
    scenario = BaseRepository(db, Scenario).create(values)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="scenario",
        entity_id=scenario.id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        new_values={"status": scenario.status.value, "name": scenario.name},
        request=request,
    )
    return _with_floor(scenario)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    request: Request,
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Revise a scenario's description, owner or drill cadence."""
    scenario = _scoped_scenario(db, scenario_id, access)
    access.require_role(scenario.organisation_id, READINESS_MANAGERS)

    update = payload.model_dump(exclude_unset=True, exclude_none=True)
    _check_references(db, update)
    update["updated_by"] = access.user.id

    BaseRepository(db, Scenario).update(scenario_id, update)
    db.refresh(scenario)

    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="scenario",
        entity_id=scenario_id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        new_values={field: audit.serialise(value) for field, value in update.items()},
        request=request,
    )
    return _with_floor(scenario)


@router.put("/{scenario_id}/playbook", response_model=ScenarioResponse)
async def set_playbook(
    request: Request,
    scenario_id: uuid.UUID,
    payload: PlaybookInput,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Replace the response plan.

    Sent whole rather than step by step: the steps are ordered, and editing
    one at a time would leave the order briefly meaningless. Rewriting the
    plan does not itself change the declared status, but it can move the floor
    beneath it — a plan that has been rewritten since the last rehearsal is
    still a plan that rehearsal did not test.
    """
    scenario = _scoped_scenario(db, scenario_id, access)
    access.require_role(scenario.organisation_id, READINESS_MANAGERS)

    readiness.require_positions_contiguous([step.position for step in payload.steps])

    scenario.playbook_steps.clear()
    db.flush()
    for step in payload.steps:
        scenario.playbook_steps.append(
            PlaybookStep(
                position=step.position,
                title=step.title,
                action=step.action,
                responsible_role=step.responsible_role,
                within_hours=step.within_hours,
                created_by=access.user.id,
                updated_by=access.user.id,
            )
        )
    scenario.updated_by = access.user.id

    db.commit()
    db.refresh(scenario)

    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="scenario",
        entity_id=scenario_id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        new_values={"playbook_steps": len(payload.steps)},
        request=request,
    )
    return _with_floor(scenario)


@router.post("/{scenario_id}/declare", response_model=ScenarioResponse)
async def declare_readiness(
    request: Request,
    scenario_id: uuid.UUID,
    payload: ReadinessDeclaration,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """State how ready the organisation is, with a reason.

    Refused if the declaration is better than the record supports, whoever
    is asking. The refusal names what is missing, so it reads as the work
    required rather than as a denial.
    """
    scenario = _scoped_scenario(db, scenario_id, access)
    access.require_role(scenario.organisation_id, READINESS_MANAGERS)

    floor = readiness.require_declarable(scenario, payload.status)

    previous = scenario.status.value
    scenario.status = payload.status
    scenario.status_rationale = payload.rationale
    scenario.status_declared_by = access.user.id
    scenario.status_declared_at = datetime.now(timezone.utc)
    scenario.updated_by = access.user.id

    db.commit()
    db.refresh(scenario)

    audit.record(
        db,
        action=audit.DECLARED,
        entity_type="scenario",
        entity_id=scenario_id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        old_values={"status": previous},
        new_values={
            "status": payload.status.value,
            "rationale": payload.rationale,
            # Recorded so the trail shows what the declaration was measured
            # against, not only what was claimed.
            "floor": floor.status.value,
        },
        request=request,
    )
    return _with_floor(scenario)


@router.get("/{scenario_id}/drills", response_model=List[DrillResponse])
async def list_drills(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Every rehearsal of this scenario, including the cancelled ones.

    Cancellations are kept deliberately: the history of what was not rehearsed
    is part of what a readiness record is for.
    """
    scenario = _scoped_scenario(db, scenario_id, access)
    return [DrillResponse.model_validate(drill) for drill in scenario.drills]


@router.post(
    "/{scenario_id}/drills", response_model=DrillResponse, status_code=status.HTTP_201_CREATED
)
async def schedule_drill(
    request: Request,
    scenario_id: uuid.UUID,
    payload: DrillSchedule,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Commit to rehearsing this scenario on a date."""
    scenario = _scoped_scenario(db, scenario_id, access)
    access.require_role(scenario.organisation_id, READINESS_MANAGERS)

    drill = Drill(
        scenario_id=scenario_id,
        scheduled_for=payload.scheduled_for,
        created_by=access.user.id,
        updated_by=access.user.id,
    )
    db.add(drill)
    db.commit()
    db.refresh(drill)

    audit.record(
        db,
        action=audit.SCHEDULED,
        entity_type="drill",
        entity_id=drill.id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        new_values={
            "scenario_id": audit.serialise(scenario_id),
            "scheduled_for": audit.serialise(payload.scheduled_for),
        },
        request=request,
    )
    return DrillResponse.model_validate(drill)


@router.post("/drills/{drill_id}/complete", response_model=DrillResponse)
async def complete_drill(
    request: Request,
    drill_id: uuid.UUID,
    payload: DrillCompletion,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Record that the rehearsal happened, and what it found.

    Completing a drill moves the scenario's floor — it may lift it, by making
    the plan tested and current, or hold it down, if the rehearsal turned up
    something critical. The declared status is deliberately left alone: a
    machine should not quietly improve a public-facing claim on somebody's
    behalf. If the floor has moved, a person declares the new status and says
    why.
    """
    drill = _scoped_drill(db, drill_id, access)
    scenario = drill.scenario
    access.require_role(scenario.organisation_id, DRILL_CONDUCTORS)
    before = audit.snapshot(drill, "status")

    if drill.status is not DrillStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a scheduled drill can be completed",
        )

    now = datetime.now(timezone.utc)
    drill.status = DrillStatus.COMPLETED
    drill.completed_at = now
    drill.conducted_by = access.user.id
    drill.summary = payload.summary
    drill.updated_by = access.user.id

    for finding in payload.findings:
        drill.findings.append(
            DrillFinding(
                description=finding.description,
                severity=finding.severity,
                raised_by=access.user.id,
                created_by=access.user.id,
                updated_by=access.user.id,
            )
        )

    # Derived from the drill record rather than typed in, so the date and the
    # account of what happened can never disagree.
    scenario.last_drill_date = now.date()
    scenario.updated_by = access.user.id

    db.commit()
    db.refresh(drill)

    audit.record(
        db,
        action=audit.COMPLETED,
        entity_type="drill",
        entity_id=drill_id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        old_values=before,
        new_values={
            "scenario_id": audit.serialise(scenario.id),
            "findings": len(payload.findings),
        },
        request=request,
    )
    return DrillResponse.model_validate(drill)


@router.post("/drills/{drill_id}/cancel", response_model=DrillResponse)
async def cancel_drill(
    request: Request,
    drill_id: uuid.UUID,
    payload: DrillCancellation,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Record that a planned rehearsal did not happen, and why.

    Cancelled rather than deleted. A scenario whose drills keep being called
    off is exactly the one a readiness review should be able to see.
    """
    drill = _scoped_drill(db, drill_id, access)
    access.require_role(drill.scenario.organisation_id, READINESS_MANAGERS)
    before = audit.snapshot(drill, "status")

    if drill.status is not DrillStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a scheduled drill can be cancelled",
        )

    drill.status = DrillStatus.CANCELLED
    drill.cancellation_reason = payload.reason
    drill.updated_by = access.user.id

    db.commit()
    db.refresh(drill)

    audit.record(
        db,
        action=audit.CANCELLED,
        entity_type="drill",
        entity_id=drill_id,
        user=access.user,
        organisation_id=drill.scenario.organisation_id,
        old_values=before,
        new_values={"reason": payload.reason},
        request=request,
    )
    return DrillResponse.model_validate(drill)


@router.post("/findings/{finding_id}/resolve", response_model=DrillFindingResponse)
async def resolve_finding(
    request: Request,
    finding_id: uuid.UUID,
    payload: FindingResolution,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Confirm that a gap a rehearsal found has been closed.

    By someone other than the person who raised it. The finder may well be the
    one who does the fixing; somebody else has to be the one who says it is
    fixed, because a critical finding is what holds the readiness colour down
    and self-certification would make that cap meaningless.
    """
    finding = BaseRepository(db, DrillFinding).get_by_id(finding_id)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    scenario = finding.drill.scenario
    if not access.can_access(scenario.organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    access.require_role(scenario.organisation_id, DRILL_CONDUCTORS)
    before = audit.snapshot(finding, "resolved_at", "resolved_by")

    if finding.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This finding is already recorded as resolved",
        )

    readiness.require_distinct_resolver(finding, access.user.id)

    finding.resolved_at = datetime.now(timezone.utc)
    finding.resolved_by = access.user.id
    finding.resolution = payload.resolution
    finding.updated_by = access.user.id

    db.commit()
    db.refresh(finding)

    audit.record(
        db,
        action=audit.RESOLVED,
        entity_type="drill_finding",
        entity_id=finding_id,
        user=access.user,
        organisation_id=scenario.organisation_id,
        old_values=before,
        new_values={
            "severity": finding.severity.value,
            "resolution": payload.resolution,
        },
        request=request,
    )
    return DrillFindingResponse.model_validate(finding)
