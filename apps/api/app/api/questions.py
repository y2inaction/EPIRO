"""Question and citizen engagement endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Question, QuestionStatus, User
from app.repositories.base import BaseRepository
from app.schemas.core import QuestionCreate, QuestionResponse

router = APIRouter()


@router.get("/", response_model=dict)
async def list_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str = Query(None),
    organisation_id: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List questions with filters."""
    query = db.query(Question)

    if organisation_id:
        query = query.filter(Question.organisation_id == organisation_id)

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
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get question by ID."""
    question_repo = BaseRepository(db, Question)
    question = question_repo.get_by_id(question_id)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    return question


@router.post("/", response_model=QuestionResponse)
async def submit_question(
    question_create: QuestionCreate,
    db: Session = Depends(get_db),
):
    """Submit a new question (public endpoint - no auth required)."""
    question_repo = BaseRepository(db, Question)
    question_data = question_create.model_dump()

    question = question_repo.create(question_data)
    return question


@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: str,
    question_update: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update question status or metadata."""
    question_repo = BaseRepository(db, Question)
    question = question_repo.get_by_id(question_id)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question_update["updated_by"] = current_user.id
    updated_question = question_repo.update(question_id, question_update)

    return updated_question


@router.post("/{question_id}/respond", response_model=QuestionResponse)
async def respond_to_question(
    question_id: str,
    response_text: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Respond to a question."""
    question_repo = BaseRepository(db, Question)
    question = question_repo.get_by_id(question_id)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question.response = response_text
    question.response_date = str(__import__("datetime").datetime.now())
    question.status = QuestionStatus.RESPONSE_DRAFTED
    question.updated_by = current_user.id

    db.commit()
    db.refresh(question)

    return question


@router.post("/{question_id}/approve", response_model=QuestionResponse)
async def approve_question_response(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve question response for publication."""
    question_repo = BaseRepository(db, Question)
    question = question_repo.get_by_id(question_id)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if not question.response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must have a response before approval",
        )

    question.status = QuestionStatus.APPROVED
    question.approved_by = current_user.id
    question.updated_by = current_user.id

    db.commit()
    db.refresh(question)

    return question


@router.post("/{question_id}/publish", response_model=QuestionResponse)
async def publish_question_response(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish question and response to public."""
    question_repo = BaseRepository(db, Question)
    question = question_repo.get_by_id(question_id)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if question.status != QuestionStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must be approved before publishing",
        )

    question.is_published = True
    question.status = QuestionStatus.PUBLISHED
    question.updated_by = current_user.id

    db.commit()
    db.refresh(question)

    return question


@router.post("/{question_id}/close", response_model=QuestionResponse)
async def close_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close a question (no further responses)."""
    question_repo = BaseRepository(db, Question)
    question = question_repo.get_by_id(question_id)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question.status = QuestionStatus.CLOSED
    question.updated_by = current_user.id

    db.commit()
    db.refresh(question)

    return question
