"""Question and citizen engagement endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.authorization import APPROVERS, PUBLISHERS, QUESTION_RESPONDERS, AccessControl, get_access
from app.database import get_db
from app.models import Question, QuestionStatus
from app.rate_limit import PUBLIC_WRITE_LIMIT, limiter
from app.repositories.base import BaseRepository
from app.schemas.core import QuestionCreate, QuestionResponse, QuestionUpdate

router = APIRouter()


def _get_scoped_question(db: Session, question_id: uuid.UUID, access: AccessControl) -> Question:
    """Load a question the caller is entitled to see."""
    question = BaseRepository(db, Question).get_by_id(question_id)
    if not question or not access.can_access(question.organisation_id):
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
            detail="Question must be assigned to an organisation first",
        )
    return question.organisation_id


@router.get("/", response_model=dict)
async def list_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List questions within the caller's organisations."""
    query = db.query(Question)

    if organisation_id:
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
    """Submit a new question (public endpoint - no auth required)."""
    question_repo = BaseRepository(db, Question)
    return question_repo.create(question_create.model_dump())


@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: uuid.UUID,
    question_update: QuestionUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update question triage metadata."""
    question = _get_scoped_question(db, question_id, access)
    access.require_role(_require_assigned_organisation(question), QUESTION_RESPONDERS)

    update_data = question_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id

    return BaseRepository(db, Question).update(question_id, update_data)


@router.post("/{question_id}/respond", response_model=QuestionResponse)
async def respond_to_question(
    question_id: uuid.UUID,
    response_text: str = Query(..., min_length=1),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Draft a response to a question."""
    question = _get_scoped_question(db, question_id, access)
    access.require_role(_require_assigned_organisation(question), QUESTION_RESPONDERS)

    question.response = response_text
    question.responded_by = access.user.id
    question.response_date = datetime.now(timezone.utc)
    question.status = QuestionStatus.RESPONSE_DRAFTED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    return question


@router.post("/{question_id}/approve", response_model=QuestionResponse)
async def approve_question_response(
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Approve a drafted response for publication."""
    question = _get_scoped_question(db, question_id, access)
    access.require_role(_require_assigned_organisation(question), APPROVERS)

    if not question.response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must have a response before approval",
        )

    access.require_distinct_actor(question.responded_by)

    question.status = QuestionStatus.APPROVED
    question.approved_by = access.user.id
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    return question


@router.post("/{question_id}/publish", response_model=QuestionResponse)
async def publish_question_response(
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Publish an approved question and response."""
    question = _get_scoped_question(db, question_id, access)
    access.require_role(_require_assigned_organisation(question), PUBLISHERS)

    if question.status != QuestionStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question must be approved before publishing",
        )

    question.is_published = True
    question.status = QuestionStatus.PUBLISHED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    return question


@router.post("/{question_id}/close", response_model=QuestionResponse)
async def close_question(
    question_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Close a question (no further responses)."""
    question = _get_scoped_question(db, question_id, access)
    access.require_role(_require_assigned_organisation(question), QUESTION_RESPONDERS)

    question.status = QuestionStatus.CLOSED
    question.updated_by = access.user.id

    db.commit()
    db.refresh(question)

    return question
