"""Field operations and missions (spec section 18).

A mission is planned, approved by somebody other than its planner and only
once a risk assessment exists, started, checked in on, and completed with a
report. Evidence gathered on it is filed against it and goes through the same
verification as anything else.

The rules live in ``app.services.missions``. Two of them are worth restating
here because they are what this module refuses to let anyone skip.

**No approval without a written risk assessment.** Sending people somewhere is
the most consequential thing the platform authorises and the only one whose
cost falls on staff rather than on a record.

**The planner may not approve their own mission.** Somebody other than the
person who wants to go has to have read the risk assessment.

On privacy: this is the part of EPIRO that records where named staff will be.
Location is held at mission level, a check-in is a state rather than a
position, and there is nowhere in the schema to put a movement trail. Spec
section 20's limit on collection is written about citizens; staff did not stop
being people by being employed. See docs/FIELD_OPERATIONS.md.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.authorization import (
    FIELD_COORDINATORS,
    FIELD_TEAM,
    AccessControl,
    get_access,
)
from app.database import get_db
from app.models import (
    Evidence,
    FieldMission,
    Geography,
    MissionCheckIn,
    MissionMember,
    MissionStatus,
    Organisation,
    Project,
    Source,
    ThematicArea,
    User,
)
from app.repositories.base import BaseRepository
from app.schemas.core import (
    CheckInInput,
    CheckInResponse,
    EvidenceResponse,
    FieldCapture,
    FieldMissionCreate,
    FieldMissionResponse,
    FieldMissionUpdate,
    MissionCancellation,
    MissionCompletion,
    MissionMemberInput,
    SafetyPostureResponse,
)
from app.services import missions

router = APIRouter()

# A mission may still be revised while it is being planned. Once somebody has
# approved it, changing where the team is going or what the risks are means
# going back for approval again.
EDITABLE = {MissionStatus.PLANNED}


def _with_safety(mission: FieldMission) -> FieldMissionResponse:
    """Serialise a mission with its current safety posture.

    Derived on read rather than stored, so it cannot be stale at exactly the
    moment it matters.
    """
    response = FieldMissionResponse.model_validate(mission)
    posture = missions.safety_posture(mission)
    response.safety = SafetyPostureResponse(
        state=posture.state,
        last_reported_at=posture.last_reported_at,
        overdue=posture.overdue,
        hours_since_report=posture.hours_since_report,
        needs_attention=posture.needs_attention,
    )
    return response


def _scoped_mission(db: Session, mission_id: uuid.UUID, access: AccessControl) -> FieldMission:
    """Load a mission the caller's organisations cover."""
    mission = BaseRepository(db, FieldMission).get_by_id(mission_id)
    if mission is None or not access.can_access(mission.organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return mission


def _check_references(db: Session, values: dict) -> None:
    """Refuse a reference to something that does not exist."""
    checks = (
        ("geography_id", Geography, "Unknown area"),
        ("project_id", Project, "Unknown project"),
        ("thematic_area_id", ThematicArea, "Unknown thematic area"),
        ("lead_id", User, "Unknown user"),
    )
    for field, model, detail in checks:
        value = values.get(field)
        if value is not None and db.get(model, value) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _add_members(
    db: Session, mission: FieldMission, members: List[MissionMemberInput], actor: User
) -> None:
    """Attach the team, refusing anyone who does not exist."""
    for member in members:
        if db.get(User, member.user_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown user on the mission team",
            )
        mission.members.append(
            MissionMember(
                user_id=member.user_id,
                role_on_mission=member.role_on_mission,
                created_by=actor.id,
                updated_by=actor.id,
            )
        )


@router.get("/", response_model=dict)
async def list_missions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[MissionStatus] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    needs_attention: bool = Query(
        False, description="Only missions that are overdue or have asked for help"
    ),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Missions within the caller's organisations, most recent first.

    ``needs_attention`` is applied after loading rather than in SQL, because
    overdue is derived from the check-in trail rather than stored. That is a
    deliberate trade: a stored flag would filter faster and would be wrong
    exactly when a team is in trouble.
    """
    query = db.query(FieldMission)

    if organisation_id:
        access.require_member(organisation_id)
        query = query.filter(FieldMission.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(FieldMission.organisation_id.in_(access.organisation_ids))

    if status_filter:
        query = query.filter(FieldMission.status == status_filter)

    if needs_attention:
        candidates = query.order_by(FieldMission.planned_start.desc()).all()
        flagged = [m for m in candidates if missions.safety_posture(m).needs_attention]
        page = flagged[skip : skip + limit]
        total = len(flagged)
    else:
        total = query.count()
        page = query.order_by(FieldMission.planned_start.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [_with_safety(mission) for mission in page],
    }


@router.get("/{mission_id}", response_model=FieldMissionResponse)
async def get_mission(
    mission_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """One mission, its team and its current safety posture."""
    return _with_safety(_scoped_mission(db, mission_id, access))


@router.post("/", response_model=FieldMissionResponse, status_code=status.HTTP_201_CREATED)
async def plan_mission(
    request: Request,
    payload: FieldMissionCreate,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Plan a field mission."""
    access.require_role(payload.organisation_id, FIELD_COORDINATORS)

    organisation = db.get(Organisation, payload.organisation_id)
    if organisation is None or not organisation.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown organisation")

    missions.require_dates_in_order(payload.planned_start, payload.planned_end)

    values = payload.model_dump(exclude={"members"})
    _check_references(db, values)
    values["created_by"] = access.user.id
    values["updated_by"] = access.user.id

    mission = FieldMission(**values)
    db.add(mission)
    db.flush()
    _add_members(db, mission, payload.members, access.user)
    db.commit()
    db.refresh(mission)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="field_mission",
        entity_id=mission.id,
        user=access.user,
        organisation_id=mission.organisation_id,
        new_values={
            "status": mission.status.value,
            "title": mission.title,
            "members": len(payload.members),
        },
        request=request,
    )
    return _with_safety(mission)


@router.put("/{mission_id}", response_model=FieldMissionResponse)
async def update_mission(
    request: Request,
    mission_id: uuid.UUID,
    payload: FieldMissionUpdate,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Revise a mission that has not yet been approved.

    Once it is approved the plan is what somebody signed off on. Changing the
    area, the window or the risks after that means planning it again rather
    than quietly editing what was approved.
    """
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_COORDINATORS)
    before = audit.snapshot(mission, "status")
    missions.require_status(
        mission,
        EDITABLE,
        "Only a mission still being planned can be edited. Cancel it and plan again.",
    )

    update = payload.model_dump(exclude_unset=True, exclude_none=True)
    _check_references(db, update)

    start = update.get("planned_start", mission.planned_start)
    end = update.get("planned_end", mission.planned_end)
    missions.require_dates_in_order(start, end)

    update["updated_by"] = access.user.id
    BaseRepository(db, FieldMission).update(mission_id, update)
    db.refresh(mission)

    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="field_mission",
        entity_id=mission_id,
        user=access.user,
        organisation_id=mission.organisation_id,
        old_values=before,
        new_values={field: audit.serialise(value) for field, value in update.items()},
        request=request,
    )
    return _with_safety(mission)


@router.post("/{mission_id}/approve", response_model=FieldMissionResponse)
async def approve_mission(
    request: Request,
    mission_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Authorise the mission to go ahead.

    Refused without a written risk assessment, and refused to the person who
    planned it. These are the two checks the whole endpoint exists for.
    """
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_COORDINATORS)
    before = audit.snapshot(mission, "status")
    missions.require_status(
        mission, {MissionStatus.PLANNED}, "Only a planned mission can be approved"
    )

    missions.require_risk_assessment(mission)
    missions.require_distinct_approver(mission, access.user.id)

    mission.status = MissionStatus.APPROVED
    mission.approved_by = access.user.id
    mission.approved_at = datetime.now(timezone.utc)
    mission.updated_by = access.user.id

    db.commit()
    db.refresh(mission)

    audit.record(
        db,
        action=audit.APPROVED,
        entity_type="field_mission",
        entity_id=mission_id,
        user=access.user,
        organisation_id=mission.organisation_id,
        old_values=before,
        new_values={"status": mission.status.value},
        request=request,
    )
    return _with_safety(mission)


@router.post("/{mission_id}/start", response_model=FieldMissionResponse)
async def start_mission(
    request: Request,
    mission_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Record that the team has set out.

    From this moment the mission is watched: a missed check-in makes it overdue
    and it appears in the attention list.
    """
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_TEAM)
    before = audit.snapshot(mission, "status")
    missions.require_status(
        mission,
        {MissionStatus.APPROVED},
        "A mission must be approved before it starts",
    )

    mission.status = MissionStatus.IN_PROGRESS
    mission.started_at = datetime.now(timezone.utc)
    mission.updated_by = access.user.id

    db.commit()
    db.refresh(mission)

    audit.record(
        db,
        action=audit.STARTED,
        entity_type="field_mission",
        entity_id=mission_id,
        user=access.user,
        organisation_id=mission.organisation_id,
        old_values=before,
        new_values={"status": mission.status.value},
        request=request,
    )
    return _with_safety(mission)


@router.post(
    "/{mission_id}/check-in", response_model=CheckInResponse, status_code=status.HTTP_201_CREATED
)
async def check_in(
    request: Request,
    mission_id: uuid.UUID,
    payload: CheckInInput,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Report that the team is all right, or that it is not.

    Carries a state and an optional note. It does not carry a position, and
    the table has no column for one: a coordinator needs to know whether
    people are safe, not to accumulate a record of where each of them went.
    """
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_TEAM)
    missions.require_status(
        mission,
        {MissionStatus.IN_PROGRESS},
        "Only a mission that is under way can be checked in on",
    )

    entry = MissionCheckIn(
        mission_id=mission_id,
        state=payload.state,
        note=payload.note,
        reported_by=access.user.id,
        created_by=access.user.id,
        updated_by=access.user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    audit.record(
        db,
        action=audit.CHECKED_IN,
        entity_type="field_mission",
        entity_id=mission_id,
        user=access.user,
        organisation_id=mission.organisation_id,
        new_values={"state": payload.state.value},
        request=request,
    )
    return CheckInResponse.model_validate(entry)


@router.get("/{mission_id}/check-ins", response_model=List[CheckInResponse])
async def list_check_ins(
    mission_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Every safety report from this mission, oldest first."""
    mission = _scoped_mission(db, mission_id, access)
    return [CheckInResponse.model_validate(entry) for entry in mission.check_ins]


@router.post("/{mission_id}/complete", response_model=FieldMissionResponse)
async def complete_mission(
    request: Request,
    mission_id: uuid.UUID,
    payload: MissionCompletion,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Record that the team is back, and what the mission found."""
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_TEAM)
    before = audit.snapshot(mission, "status")
    missions.require_status(
        mission,
        {MissionStatus.IN_PROGRESS},
        "Only a mission that is under way can be completed",
    )

    mission.status = MissionStatus.COMPLETED
    mission.completed_at = datetime.now(timezone.utc)
    mission.report = payload.report
    mission.updated_by = access.user.id

    db.commit()
    db.refresh(mission)

    audit.record(
        db,
        action=audit.COMPLETED,
        entity_type="field_mission",
        entity_id=mission_id,
        user=access.user,
        organisation_id=mission.organisation_id,
        old_values=before,
        new_values={"status": mission.status.value},
        request=request,
    )
    return _with_safety(mission)


@router.post("/{mission_id}/cancel", response_model=FieldMissionResponse)
async def cancel_mission(
    request: Request,
    mission_id: uuid.UUID,
    payload: MissionCancellation,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Call off a mission that has not been completed, with a reason.

    A mission already under way can be called off: that is a recall, and it is
    the case where a stated reason matters most.
    """
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_COORDINATORS)
    missions.require_status(
        mission,
        {MissionStatus.PLANNED, MissionStatus.APPROVED, MissionStatus.IN_PROGRESS},
        "A completed mission cannot be cancelled",
    )

    previous = mission.status.value
    mission.status = MissionStatus.CANCELLED
    mission.cancellation_reason = payload.reason
    mission.updated_by = access.user.id

    db.commit()
    db.refresh(mission)

    audit.record(
        db,
        action=audit.CANCELLED,
        entity_type="field_mission",
        entity_id=mission_id,
        user=access.user,
        organisation_id=mission.organisation_id,
        old_values={"status": previous},
        new_values={"status": mission.status.value, "reason": payload.reason},
        request=request,
    )
    return _with_safety(mission)


@router.post(
    "/{mission_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED
)
async def capture_evidence(
    request: Request,
    response: Response,
    mission_id: uuid.UUID,
    payload: FieldCapture,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """File an observation gathered on this mission.

    **Idempotent on ``capture_key``.** A device on a bad connection retries,
    and a capture endpoint that filed the same observation twice could not be
    built on later. A repeat of a key this organisation has already used
    returns the record that was created the first time, with 200 rather than
    201, so a client can tell the difference.

    The record starts as an unverified draft like any other. Going and looking
    is how evidence is gathered; it is not a reason to skip verification.
    """
    mission = _scoped_mission(db, mission_id, access)
    access.require_role(mission.organisation_id, FIELD_TEAM)
    missions.require_capturable(mission)

    existing = (
        db.query(Evidence)
        .filter(
            Evidence.organisation_id == mission.organisation_id,
            Evidence.capture_key == payload.capture_key,
        )
        .first()
    )
    if existing is not None:
        # The retry case. Deliberately not an error: the client did the right
        # thing, and the correct answer is the record it already created. The
        # status has to be set on the response object because the decorator's
        # 201 applies to the whole route — returning early does not change it,
        # and a retry answered with 201 would tell the client it had just
        # created a second record.
        response.status_code = status.HTTP_200_OK
        return EvidenceResponse.model_validate(existing)

    source = db.get(Source, payload.source_id)
    if source is None or not access.can_access(source.organisation_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown source")

    values = payload.model_dump()
    _check_references(db, values)
    values.update(missions.captured_evidence_defaults(mission))
    values["created_by"] = access.user.id
    values["updated_by"] = access.user.id

    evidence = Evidence(**values)
    db.add(evidence)
    try:
        db.commit()
    except IntegrityError:
        # Two retries of the same capture arriving at once both looked, both
        # found nothing, and both tried to insert. The partial unique index
        # settles it, and the loser's correct answer is the record the winner
        # created — not a 500. The check above handles the common case; this
        # handles the race, and without it the promise that a retry is safe
        # would hold only when the retries were far enough apart.
        db.rollback()
        winner = (
            db.query(Evidence)
            .filter(
                Evidence.organisation_id == mission.organisation_id,
                Evidence.capture_key == payload.capture_key,
            )
            .first()
        )
        if winner is None:
            raise
        response.status_code = status.HTTP_200_OK
        return EvidenceResponse.model_validate(winner)

    db.refresh(evidence)

    audit.record(
        db,
        action=audit.CAPTURED,
        entity_type="evidence",
        entity_id=evidence.id,
        user=access.user,
        organisation_id=mission.organisation_id,
        evidence_id=evidence.id,
        new_values={
            "field_mission_id": audit.serialise(mission_id),
            "reference": evidence.reference,
        },
        request=request,
    )
    return EvidenceResponse.model_validate(evidence)


@router.get("/{mission_id}/evidence", response_model=List[EvidenceResponse])
async def list_mission_evidence(
    mission_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Everything this mission brought back."""
    mission = _scoped_mission(db, mission_id, access)

    records = (
        db.query(Evidence)
        .filter(Evidence.field_mission_id == mission.id)
        .order_by(Evidence.created_at)
        .all()
    )
    return [EvidenceResponse.model_validate(record) for record in records]
