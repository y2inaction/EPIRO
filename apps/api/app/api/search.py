"""Global search endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from app.authorization import AccessControl, get_access
from app.database import get_db
from app.models import Evidence, Project, Question, Story
from app.schemas.core import EvidenceResponse, QuestionResponse, StoryResponse

router = APIRouter()


@router.get("/")
async def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    content_type: Optional[str] = Query(None),  # evidence, story, question, project
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Search across content the caller's organisations own."""
    organisation_ids = access.organisation_ids

    def scoped(query: SAQuery, model: Any) -> SAQuery:
        """Restrict a query to the caller's organisations."""
        if access.is_platform_admin:
            return query
        return query.filter(model.organisation_id.in_(organisation_ids))

    evidence_results: list[EvidenceResponse] = []
    story_results: list[StoryResponse] = []
    question_results: list[QuestionResponse] = []
    project_results: list[dict[str, Any]] = []
    total = 0

    # A caller who belongs to no organisation can see nothing.
    if not organisation_ids and not access.is_platform_admin:
        return {
            "evidence": evidence_results,
            "stories": story_results,
            "questions": question_results,
            "projects": project_results,
            "total": total,
        }

    if not content_type or content_type == "evidence":
        evidence_query = scoped(
            db.query(Evidence).filter(
                or_(
                    Evidence.title.ilike(f"%{q}%"),
                    Evidence.description.ilike(f"%{q}%"),
                )
            ),
            Evidence,
        )
        total += evidence_query.count()
        evidence_results = [
            EvidenceResponse.model_validate(item)
            for item in evidence_query.offset(skip).limit(limit).all()
        ]

    if not content_type or content_type == "story":
        story_query = scoped(
            db.query(Story).filter(
                or_(
                    Story.title.ilike(f"%{q}%"),
                    Story.headline.ilike(f"%{q}%"),
                    Story.body.ilike(f"%{q}%"),
                )
            ),
            Story,
        )
        total += story_query.count()
        story_results = [
            StoryResponse.model_validate(item)
            for item in story_query.offset(skip).limit(limit).all()
        ]

    if not content_type or content_type == "question":
        question_query = scoped(
            db.query(Question).filter(Question.question_text.ilike(f"%{q}%")),
            Question,
        )
        total += question_query.count()
        question_results = [
            QuestionResponse.model_validate(item)
            for item in question_query.offset(skip).limit(limit).all()
        ]

    if not content_type or content_type == "project":
        project_query = scoped(
            db.query(Project).filter(
                or_(
                    Project.name.ilike(f"%{q}%"),
                    Project.description.ilike(f"%{q}%"),
                )
            ),
            Project,
        )
        total += project_query.count()
        project_results = [
            {
                "id": item.id,
                "name": item.name,
                "code": item.code,
                "description": item.description,
            }
            for item in project_query.offset(skip).limit(limit).all()
        ]

    return {
        "evidence": evidence_results,
        "stories": story_results,
        "questions": question_results,
        "projects": project_results,
        "total": total,
    }
