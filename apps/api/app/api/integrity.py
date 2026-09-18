"""Information integrity endpoints (spec sections 25-26).

A claim is logged, claimed by a body, assessed against evidence, signed off by
somebody other than the assessor, and answered in public by somebody other than
the approver. The rules that decide what may happen live in
``app.services.integrity``; this module is the wiring.

Two limits are deliberate and stated here rather than left to be discovered.

There is no public submission endpoint. A member of the public reporting "I saw
this going round" would be useful, and it is also a channel for reporting each
other; spec section 20 limits collection to what legitimate operation needs, so
the first version keeps logging to staff. See docs/STATUS.md.

Nothing in the request or response shape refers to who spread a claim. The
model has no column for it either — the prohibition in spec section 4 is
enforced by there being nowhere to put such a thing, not by remembering not to.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
from app.authorization import (
    APPROVERS,
    INTEGRITY_ASSESSORS,
    INTEGRITY_MONITORS,
    PUBLISHERS,
    AccessControl,
    get_access,
)
from app.database import get_db
from app.models import (
    ApprovalDecision,
    Evidence,
    Geography,
    IntegritySignal,
    IntegritySignalPriority,
    IntegritySignalStatus,
    Organisation,
    ThematicArea,
    User,
)
from app.repositories.base import BaseRepository
from app.schemas.core import (
    ApprovalDecisionRequest,
    ApprovalRecordResponse,
    IntegrityAssessment,
    IntegrityResponseDraft,
    IntegritySignalCreate,
    IntegritySignalResponse,
    IntegritySignalUpdate,
    RejectionRequest,
    WithdrawalRequest,
)
from app.services import integrity
from app.services.approval import INTEGRITY_SIGNAL, decisions_for, record_decision

router = APIRouter()


def _scoped_signal(db: Session, signal_id: uuid.UUID, access: AccessControl) -> IntegritySignal:
    """Load a signal the caller's organisations cover.

    Reported as missing rather than forbidden, so the endpoint does not confirm
    that another body is looking into something.
    """
    signal = BaseRepository(db, IntegritySignal).get_by_id(signal_id)
    if signal is None or not access.can_access(signal.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integrity signal not found",
        )
    return signal


def _check_references(db: Session, values: dict) -> None:
    """Refuse a reference to something that does not exist."""
    geography_id = values.get("geography_id")
    if geography_id is not None and db.get(Geography, geography_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown area")

    thematic_area_id = values.get("thematic_area_id")
    if thematic_area_id is not None and db.get(ThematicArea, thematic_area_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown thematic area")

    assigned_to = values.get("assigned_to")
    if assigned_to is not None and db.get(User, assigned_to) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user")


@router.get("/", response_model=dict)
async def list_signals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[IntegritySignalStatus] = Query(None),
    priority: Optional[IntegritySignalPriority] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Signals within the caller's organisations, most urgent first."""
    query = db.query(IntegritySignal)

    if organisation_id:
        access.require_member(organisation_id)
        query = query.filter(IntegritySignal.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(IntegritySignal.organisation_id.in_(access.organisation_ids))

    if status_filter:
        query = query.filter(IntegritySignal.status == status_filter)
    if priority:
        query = query.filter(IntegritySignal.priority == priority)

    total = query.count()
    signals = query.order_by(IntegritySignal.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [IntegritySignalResponse.model_validate(signal) for signal in signals],
    }


@router.get("/{signal_id}", response_model=IntegritySignalResponse)
async def get_signal(
    signal_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """One integrity signal."""
    return _scoped_signal(db, signal_id, access)


@router.post("/", response_model=IntegritySignalResponse, status_code=status.HTTP_201_CREATED)
async def log_signal(
    request: Request,
    payload: IntegritySignalCreate,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Log a claim that is circulating and needs looking at."""
    access.require_role(payload.organisation_id, INTEGRITY_MONITORS)

    organisation = db.get(Organisation, payload.organisation_id)
    if organisation is None or not organisation.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown organisation")

    values = payload.model_dump()
    _check_references(db, values)

    values["created_by"] = access.user.id
    values["updated_by"] = access.user.id
    signal = BaseRepository(db, IntegritySignal).create(values)

    audit.record(
        db,
        action=audit.CREATED,
        entity_type="integrity_signal",
        entity_id=signal.id,
        user=access.user,
        organisation_id=signal.organisation_id,
        new_values={
            "status": signal.status.value,
            "priority": signal.priority.value,
        },
        request=request,
    )
    return signal


@router.put("/{signal_id}", response_model=IntegritySignalResponse)
async def update_signal(
    request: Request,
    signal_id: uuid.UUID,
    payload: IntegritySignalUpdate,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Revise a signal.

    Rewording the claim invalidates any assessment of it: the finding answered
    the old wording. Changing the priority or the owner does not, so those do
    not throw away work.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, INTEGRITY_MONITORS)

    if signal.status is IntegritySignalStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A published correction cannot be edited. Withdraw it if what "
                "was published no longer stands."
            ),
        )

    update = payload.model_dump(exclude_unset=True, exclude_none=True)
    _check_references(db, update)

    if integrity.changes_the_claim(update, signal):
        update.update(integrity.invalidate_assessment(signal))

    update["updated_by"] = access.user.id
    updated = BaseRepository(db, IntegritySignal).update(signal_id, update)

    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        new_values={field: audit.serialise(value) for field, value in update.items()},
        request=request,
    )
    return updated


@router.post("/{signal_id}/assess", response_model=IntegritySignalResponse)
async def assess_signal(
    request: Request,
    signal_id: uuid.UUID,
    payload: IntegrityAssessment,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Record what was found out about the claim, and why.

    The finding and the reasoning are written together. A verdict with no
    reasoning would be exactly the unexplainable intelligence spec section 4
    rules out, so the request schema cannot express one.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, INTEGRITY_ASSESSORS)
    integrity.require_status(
        signal,
        integrity.ASSESSABLE,
        "Only a signal that has not been approved can be assessed",
    )

    if payload.evidence_id is not None:
        evidence = db.get(Evidence, payload.evidence_id)
        if evidence is None or not access.can_access(evidence.organisation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown evidence record",
            )

    signal.finding = payload.finding
    signal.assessment = payload.assessment
    signal.impact = payload.impact
    signal.evidence_id = payload.evidence_id
    signal.assessed_by = access.user.id
    signal.assessed_at = datetime.now(timezone.utc)
    signal.status = IntegritySignalStatus.ASSESSED
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    audit.record(
        db,
        action=audit.ASSESSED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        evidence_id=signal.evidence_id,
        new_values={
            "status": signal.status.value,
            "finding": signal.finding.value if signal.finding else None,
        },
        request=request,
    )
    return signal


@router.post("/{signal_id}/respond", response_model=IntegritySignalResponse)
async def draft_response(
    request: Request,
    signal_id: uuid.UUID,
    payload: IntegrityResponseDraft,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Draft the correction the body intends to put out.

    Allowed before or after approval of the finding, but not after the
    correction has been published: what is public is changed by withdrawing it.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, INTEGRITY_ASSESSORS)
    integrity.require_status(
        signal,
        integrity.ASSESSABLE | {IntegritySignalStatus.APPROVED},
        "A response cannot be drafted against a published or closed signal",
    )

    signal.response = payload.response
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    audit.record(
        db,
        action=audit.RESPONDED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        new_values={"status": signal.status.value},
        request=request,
    )
    return signal


@router.post("/{signal_id}/approve", response_model=IntegritySignalResponse)
async def approve_signal(
    request: Request,
    signal_id: uuid.UUID,
    decision: Optional[ApprovalDecisionRequest] = None,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Sign off a finding so the correction can be published.

    Two things are checked that nothing else checks: the finding cites evidence
    the organisation has itself approved, and the person signing it off is not
    the person who wrote it.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, APPROVERS)
    integrity.require_status(
        signal,
        {IntegritySignalStatus.ASSESSED},
        "Only an assessed signal can be approved",
    )

    evidence = db.get(Evidence, signal.evidence_id) if signal.evidence_id else None
    integrity.require_source_link(signal, evidence)
    access.require_distinct_actor(signal.assessed_by)

    signal.status = IntegritySignalStatus.APPROVED
    signal.approved_by = access.user.id
    signal.approved_at = datetime.now(timezone.utc)
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    record_decision(
        db,
        entity_type=INTEGRITY_SIGNAL,
        entity_id=signal_id,
        organisation_id=signal.organisation_id,
        decision=ApprovalDecision.APPROVED,
        reviewer=access.user,
        comments=decision.comments if decision else None,
        entity_version=signal.version,
    )

    audit.record(
        db,
        action=audit.APPROVED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        evidence_id=signal.evidence_id,
        new_values={"status": signal.status.value},
        request=request,
    )
    return signal


@router.post("/{signal_id}/reject", response_model=IntegritySignalResponse)
async def reject_signal(
    request: Request,
    signal_id: uuid.UUID,
    rejection: RejectionRequest,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Send an assessment back, with a reason."""
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, APPROVERS)
    integrity.require_status(
        signal,
        {IntegritySignalStatus.ASSESSED, IntegritySignalStatus.APPROVED},
        "Only an assessed or approved signal can be rejected",
    )

    previous = signal.status.value
    signal.status = IntegritySignalStatus.ASSESSING
    # An approval that has been overturned must not be left on the record.
    signal.approved_by = None
    signal.approved_at = None
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    record_decision(
        db,
        entity_type=INTEGRITY_SIGNAL,
        entity_id=signal_id,
        organisation_id=signal.organisation_id,
        decision=(
            ApprovalDecision.CHANGES_REQUESTED
            if rejection.changes_requested
            else ApprovalDecision.REJECTED
        ),
        reviewer=access.user,
        comments=rejection.comments,
        entity_version=signal.version,
    )

    audit.record(
        db,
        action=audit.REJECTED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        old_values={"status": previous},
        new_values={"status": signal.status.value, "comments": rejection.comments},
        request=request,
    )
    return signal


@router.post("/{signal_id}/publish", response_model=IntegritySignalResponse)
async def publish_response(
    request: Request,
    signal_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Put the correction out publicly.

    The evidence is re-checked here and not only at approval, because it can be
    withdrawn in between. A correction resting on a record the organisation has
    since taken back must not go out on the strength of an approval given while
    it still stood.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, PUBLISHERS)
    integrity.require_status(
        signal,
        {IntegritySignalStatus.APPROVED},
        "A correction must be approved before it is published",
    )

    integrity.publishable_response(signal)
    evidence = db.get(Evidence, signal.evidence_id) if signal.evidence_id else None
    integrity.require_source_link(signal, evidence)

    # The approver signed off the finding; someone else releases it.
    access.require_distinct_actor(signal.approved_by)

    signal.status = IntegritySignalStatus.PUBLISHED
    signal.published_at = datetime.now(timezone.utc)
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    audit.record(
        db,
        action=audit.PUBLISHED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        evidence_id=signal.evidence_id,
        new_values={
            "status": signal.status.value,
            "approved_by": audit.serialise(signal.approved_by),
        },
        request=request,
    )
    return signal


@router.post("/{signal_id}/withdraw", response_model=IntegritySignalResponse)
async def withdraw_response(
    request: Request,
    signal_id: uuid.UUID,
    withdrawal: WithdrawalRequest,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Take back a published correction, with a stated reason.

    A correction that turns out to be wrong is the worst thing on the platform
    to leave standing, so it is withdrawn rather than deleted: the record keeps
    what was said and why it no longer stands.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, PUBLISHERS)
    integrity.require_status(
        signal,
        {IntegritySignalStatus.PUBLISHED},
        "Only a published correction can be withdrawn",
    )

    signal.status = IntegritySignalStatus.WITHDRAWN
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    audit.record(
        db,
        action=audit.WITHDRAWN,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        old_values={"status": IntegritySignalStatus.PUBLISHED.value},
        new_values={
            "status": signal.status.value,
            "reason": withdrawal.reason,
        },
        request=request,
    )
    return signal


@router.post("/{signal_id}/close", response_model=IntegritySignalResponse)
async def close_signal(
    request: Request,
    signal_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Close a signal that needs no further work.

    A published correction is not closed this way: it stays published until it
    is withdrawn, so that closing a case cannot quietly remove something the
    public has already been told.
    """
    signal = _scoped_signal(db, signal_id, access)
    access.require_role(signal.organisation_id, INTEGRITY_MONITORS)

    if signal.status is IntegritySignalStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Withdraw a published correction rather than closing it",
        )

    previous = signal.status.value
    signal.status = IntegritySignalStatus.CLOSED
    signal.updated_by = access.user.id

    db.commit()
    db.refresh(signal)

    audit.record(
        db,
        action=audit.CLOSED,
        entity_type="integrity_signal",
        entity_id=signal_id,
        user=access.user,
        organisation_id=signal.organisation_id,
        old_values={"status": previous},
        new_values={"status": signal.status.value},
        request=request,
    )
    return signal


@router.get("/{signal_id}/approvals", response_model=list[ApprovalRecordResponse])
async def list_signal_approvals(
    signal_id: uuid.UUID,
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Every approval decision made against this assessment, oldest first."""
    _scoped_signal(db, signal_id, access)

    return [
        ApprovalRecordResponse.model_validate(record)
        for record in decisions_for(db, INTEGRITY_SIGNAL, signal_id)
    ]
