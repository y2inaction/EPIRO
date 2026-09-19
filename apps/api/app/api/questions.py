"""Question and citizen engagement endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
from app.authorization import APPROVERS, PUBLISHERS, QUESTION_RESPONDERS, AccessControl, get_access
from app.database import get_db
from app.models import (
    ApprovalDecision,
    Geography,
    Organisation,
    Question,
    QuestionStatus,
    User,
)
from app.rate_limit import PUBLIC_WRITE_LIMIT, limiter
from app.repositories.base import BaseRepository
from app.schemas.core import (
    ApprovalDecisionRequest,
    ApprovalRecordResponse,
    QuestionCreate,
    QuestionResponse,
    QuestionResponseDraft,
    QuestionTriage,
    QuestionUpdate,
    RejectionRequest,
)
from app.services.approval import QUESTION, decisions_for, record_decision

router = APIRouter()

# A question can be answered from triage onwards, and a rejected draft is
# rewritten rather than started again.
RESPONDABLE = frozenset(
    {
        QuestionStatus.TRIAGED,
        QuestionStatus.RESEARCHING,
        QuestionStatus.VERIFIED,
        QuestionStatus.RESPONSE_DRAFTED,
    }
)


def _get_scoped_question(db: Session, question_id: uuid.UUID, access: AccessControl) -> Question:
    """Load a question the caller is entitled to see.

    An untriaged question belongs to no organisation, so ordinary tenant
    scoping would hide it from everyone — including the people the inbox
    offers it to. Anyone who could claim one may read one: otherwise a
    question could be listed in the queue and not opened, which is exactly
    the dead end triage exists to remove.
    """
    question = BaseRepository(db, Question).get_by_id(question_id)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if question.organisation_id is None:
        if access.is_platform_admin or access.holds_role_anywhere(QUESTION_RESPONDERS):
            return question
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if not access.can_access(question.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    return question


def _require_assigned_organisation(question: Question) -> uuid.UUID:
    """Return the question's organisation, refusing unassigned questions.

    A question submitted publicly has no organisation until it is triaged, and
    there is no organisation against which to check a role until it does.
    """
    if question.organisation_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question must be triaged to an organisation first",
        )
    return question.organisation_id


def _require_status(question: Question, allowed, detail: str) -> None:
    """Refuse a transition the question's current state does not allow."""
    if question.status not in allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("/", response_model=dict)
async def list_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[QuestionStatus] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    untriaged: bool = Query(
        False, description="The public inbox: questions not yet assigned to a body"
    ),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List questions within the caller's organisations.

    An untriaged question belongs to no organisation, so tenant scoping would
    hide the public inbox from everyone. It is listed separately, for callers
    who could triage one.
    """
    query = db.query(Question)

    if untriaged:
        if not access.is_platform_admin and not access.holds_role_anywhere(QUESTION_RESPONDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have a role that can triage questions",
            )
        query = query.filter(Question.organisation_id.is_(None))
    elif organisation_id:
        access.require_member(organisation_id)
        query = query.filter(Question.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(Question.organisation_id.in_(access.organisation_ids))

    if status_filter:
        query = query.filter(Question.status == status_filter)

    total = query.count()
    questions = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [QuestionResponse.model_validate(q) for q in questions],
    }


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get question by ID."""
    return _get_scoped_question(db, question_id, access)


@router.post("/", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(PUBLIC_WRITE_LIMIT)
async def submit_question(
    request: Request,
    question_create: QuestionCreate,
    db: Session = Depends(get_db),
):
    """Submit a new question. Public: no authentication required."""
    payload = question_create.model_dump()

    organisation_id = payload.get("organisation_id")
    if organisation_id is not None:
        organisation = db.get(Organisation, organisation_id)
        if organisation is None or not organisation.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown organisation",
            )

    question = BaseRepository(db, Question).create(payload)

    # Deliberately records nothing about who submitted it. The audit trail
    # exists to hold the organisation to account for how it handled a
    # question, not to build a record of the people who ask them.
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="question",
        entity_id=question.id,
        organisation_id=question.organisation_id,
        new_values={"status": question.status.value, "language": question.language},
    )
    return question


@router.post("/{question_id}/triage", response_model=QuestionResponse)
async def triage_question(
    request: Request,
    question_id: uuid.UUID,
    triage: QuestionTriage,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Assign an untriaged question to the body that will answer it.

    The role is checked against the organisation the question is being taken
    into, because until now there was none to check against — which left every
    publicly submitted question permanently stuck.
    """
    question = BaseRepository(db, Question).get_by_id(question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    if question.organisation_id is not None and not access.can_access(question.organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    access.require_role(triage.organisation_id, QUESTION_RESPONDERS)
    before = audit.snapshot(question, "status", "organisation_id")

    if question.status is not QuestionStatus.NEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a new question can be triaged",
        )

    if triage.geography_id is not None and db.get(Geography, triage.geography_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown area")

    if triage.assigned_to is not None and db.get(User, triage.assigned_to) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user")

    question.organisation_id = triage.organisation_id
    question.geography_id = triage.geography_id
    question.assigned_to = triage.assigned_to
    if triage.category is not None:
        question.category = triage.category
    question.status = QuestionStatus.TRIAGED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    audit.record(
        db,
        action=audit.TRIAGED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=question.organisation_id,
        old_values=before,
        new_values={
            "status": QuestionStatus.TRIAGED.value,
            "organisation_id": audit.serialise(triage.organisation_id),
            "geography_id": audit.serialise(triage.geography_id),
        },
        request=request,
    )
    return question


@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    request: Request,
    question_id: uuid.UUID,
    question_update: QuestionUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update question triage metadata."""
    question = _get_scoped_question(db, question_id, access)
    organisation_id = _require_assigned_organisation(question)
    access.require_role(organisation_id, QUESTION_RESPONDERS)
    before = audit.snapshot(question, "status", "category")

    update_data = question_update.model_dump(exclude_unset=True)

    geography_id = update_data.get("geography_id")
    if geography_id is not None and db.get(Geography, geography_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown area")

    update_data["updated_by"] = access.user.id

    updated = BaseRepository(db, Question).update(question_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=before,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.post("/{question_id}/respond", response_model=QuestionResponse)
async def respond_to_question(
    request: Request,
    question_id: uuid.UUID,
    draft: QuestionResponseDraft,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Draft a response to a question."""
    question = _get_scoped_question(db, question_id, access)
    organisation_id = _require_assigned_organisation(question)
    access.require_role(organisation_id, QUESTION_RESPONDERS)
    before = audit.snapshot(question, "status")
    _require_status(
        question,
        RESPONDABLE,
        "A response can only be drafted for a question that has been triaged and not yet approved",
    )

    question.response = draft.response
    question.responded_by = access.user.id
    question.response_date = datetime.now(timezone.utc)
    question.status = QuestionStatus.RESPONSE_DRAFTED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    audit.record(
        db,
        action=audit.RESPONDED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=before,
        new_values={"status": QuestionStatus.RESPONSE_DRAFTED.value},
        request=request,
    )
    return question


@router.post("/{question_id}/approve", response_model=QuestionResponse)
async def approve_question_response(
    request: Request,
    question_id: uuid.UUID,
    decision: Optional[ApprovalDecisionRequest] = None,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Approve a drafted response for publication."""
    question = _get_scoped_question(db, question_id, access)
    organisation_id = _require_assigned_organisation(question)
    access.require_role(organisation_id, APPROVERS)
    before = audit.snapshot(question, "status")

    if not question.response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must have a response before approval",
        )

    _require_status(
        question,
        {QuestionStatus.RESPONSE_DRAFTED},
        "Only a drafted response can be approved",
    )
    access.require_distinct_actor(question.responded_by)

    question.status = QuestionStatus.APPROVED
    question.approved_by = access.user.id
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    record_decision(
        db,
        entity_type=QUESTION,
        entity_id=question_id,
        organisation_id=organisation_id,
        decision=ApprovalDecision.APPROVED,
        reviewer=access.user,
        comments=decision.comments if decision else None,
    )

    audit.record(
        db,
        action=audit.APPROVED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=before,
        new_values={"status": QuestionStatus.APPROVED.value},
        request=request,
    )
    return question


@router.post("/{question_id}/reject", response_model=QuestionResponse)
async def reject_question_response(
    request: Request,
    question_id: uuid.UUID,
    rejection: RejectionRequest,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Send a drafted or approved response back, with a reason.

    Without this an answer that was wrong could only be approved or left
    sitting: there was no way to record that it had been refused, or why.
    """
    question = _get_scoped_question(db, question_id, access)
    organisation_id = _require_assigned_organisation(question)
    access.require_role(organisation_id, APPROVERS)
    _require_status(
        question,
        {QuestionStatus.RESPONSE_DRAFTED, QuestionStatus.APPROVED},
        "Only a drafted or approved response can be rejected",
    )

    previous = question.status.value
    question.status = QuestionStatus.RESEARCHING
    # An approval that has been overturned must not be left on the record.
    question.approved_by = None
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    record_decision(
        db,
        entity_type=QUESTION,
        entity_id=question_id,
        organisation_id=organisation_id,
        decision=(
            ApprovalDecision.CHANGES_REQUESTED
            if rejection.changes_requested
            else ApprovalDecision.REJECTED
        ),
        reviewer=access.user,
        comments=rejection.comments,
    )

    audit.record(
        db,
        action=audit.REJECTED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values={"status": previous},
        new_values={
            "status": QuestionStatus.RESEARCHING.value,
            "comments": rejection.comments,
        },
        request=request,
    )
    return question


@router.get("/{question_id}/approvals", response_model=list[ApprovalRecordResponse])
async def list_question_approvals(
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Every approval decision made against this response, oldest first."""
    _get_scoped_question(db, question_id, access)

    return [
        ApprovalRecordResponse.model_validate(record)
        for record in decisions_for(db, QUESTION, question_id)
    ]


@router.post("/{question_id}/publish", response_model=QuestionResponse)
async def publish_question_response(
    request: Request,
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Publish an approved question and response."""
    question = _get_scoped_question(db, question_id, access)
    organisation_id = _require_assigned_organisation(question)
    access.require_role(organisation_id, PUBLISHERS)
    before = audit.snapshot(question, "status", "is_published")
    _require_status(
        question,
        {QuestionStatus.APPROVED},
        "Question must be approved before publishing",
    )

    # The approver signed off the answer; someone else releases it.
    access.require_distinct_actor(question.approved_by)

    approved_by = question.approved_by
    question.is_published = True
    question.status = QuestionStatus.PUBLISHED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    audit.record(
        db,
        action=audit.PUBLISHED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=before,
        new_values={
            "status": QuestionStatus.PUBLISHED.value,
            "approved_by": audit.serialise(approved_by),
        },
        request=request,
    )
    return question


@router.post("/{question_id}/close", response_model=QuestionResponse)
async def close_question(
    request: Request,
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Close a question (no further responses)."""
    question = _get_scoped_question(db, question_id, access)
    organisation_id = _require_assigned_organisation(question)
    access.require_role(organisation_id, QUESTION_RESPONDERS)

    previous = question.status.value
    question.status = QuestionStatus.CLOSED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    audit.record(
        db,
        action=audit.CLOSED,
        entity_type="question",
        entity_id=question_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values={"status": previous},
        new_values={"status": QuestionStatus.CLOSED.value},
        request=request,
    )
    return question
