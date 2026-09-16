"""Global search endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import User, Evidence, Story, Question, Project
from app.schemas.core import (
    EvidenceResponse,
    StoryResponse,
    QuestionResponse,
)
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    content_type: str = Query(None),  # evidence, story, question, project
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search across all content types."""
    results = {
        "evidence": [],
        "stories": [],
        "questions": [],
        "projects": [],
        "total": 0,
    }

    # Search evidence
    if not content_type or content_type == "evidence":
        evidence_query = db.query(Evidence).filter(
            or_(
                Evidence.title.ilike(f"%{q}%"),
                Evidence.description.ilike(f"%{q}%"),
            )
        )
        evidence_total = evidence_query.count()
        evidence_items = evidence_query.offset(skip).limit(limit).all()

        results["evidence"] = [
            EvidenceResponse.model_validate(item) for item in evidence_items
        ]
        results["total"] += evidence_total

    # Search stories
    if not content_type or content_type == "story":
        story_query = db.query(Story).filter(
            or_(
                Story.title.ilike(f"%{q}%"),
                Story.headline.ilike(f"%{q}%"),
                Story.body.ilike(f"%{q}%"),
            )
        )
        story_total = story_query.count()
        story_items = story_query.offset(skip).limit(limit).all()

        results["stories"] = [
            StoryResponse.model_validate(item) for item in story_items
        ]
        results["total"] += story_total

    # Search questions
    if not content_type or content_type == "question":
        question_query = db.query(Question).filter(
            Question.question_text.ilike(f"%{q}%")
        )
        question_total = question_query.count()
        question_items = question_query.offset(skip).limit(limit).all()

        results["questions"] = [
            QuestionResponse.model_validate(item) for item in question_items
        ]
        results["total"] += question_total

    # Search projects
    if not content_type or content_type == "project":
        project_query = db.query(Project).filter(
            or_(
                Project.name.ilike(f"%{q}%"),
                Project.description.ilike(f"%{q}%"),
            )
        )
        project_total = project_query.count()
        project_items = project_query.offset(skip).limit(limit).all()

        results["projects"] = [
            {
                "id": item.id,
                "name": item.name,
                "code": item.code,
                "description": item.description,
            }
            for item in project_items
        ]
        results["total"] += project_total

    return results
