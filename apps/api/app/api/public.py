"""The public information portal.

Everything the platform publishes was, until now, only reachable with
credentials: the public information system had no public. These endpoints need
no authentication and serve only what has actually completed its approval
workflow and been published.

Three rules hold across this module, and the tests assert all three:

1. Only published records are ever returned. Draft, rejected and withdrawn
   content does not appear, and neither does anything still under review.
2. Responses are built from the allow-list schemas in app.schemas.public, so an
   internal field cannot reach the portal by being added to a model.
3. No individual is identified. Not the author, verifier, approver or
   publisher, and not the person who submitted a question.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Evidence,
    EvidenceStatus,
    Organisation,
    Question,
    QuestionStatus,
    Story,
    StoryStatus,
)
from app.rate_limit import PUBLIC_READ_LIMIT, limiter
from app.schemas.public import (
    PublicEvidence,
    PublicOrganisation,
    PublicPage,
    PublicQuestion,
    PublicStory,
)
from app.services.search import build_tsquery

router = APIRouter()


def _organisation(organisation: Optional[Organisation]) -> Optional[PublicOrganisation]:
    """The publishing body, or nothing when a record has no owner."""
    if organisation is None:
        return None
    return PublicOrganisation.model_validate(organisation)


def _story(story: Story) -> PublicStory:
    """Serialise a story for the portal, with its evidence citation."""
    public = PublicStory.model_validate(story)
    public.organisation = _organisation(story.organisation)
    # The citation is the point of the platform: a reader can follow the claim
    # back to the record it rests on.
    public.evidence_reference = story.evidence.reference if story.evidence else None
    return public


def _evidence(evidence: Evidence) -> PublicEvidence:
    """Serialise an evidence record for the portal."""
    public = PublicEvidence.model_validate(evidence)
    public.organisation = _organisation(evidence.organisation)
    return public


def _question(question: Question) -> PublicQuestion:
    """Serialise a published question and its answer."""
    public = PublicQuestion.model_validate(question)
    public.organisation = _organisation(question.organisation)
    return public


def _page(total: int, skip: int, limit: int, data: List[Any]) -> Dict[str, Any]:
    """Wrap a slice of results in the standard envelope."""
    return PublicPage(
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit,
        data=[item.model_dump(mode="json") for item in data],
    ).model_dump()


def _published_stories(db: Session):
    """Stories that completed approval and were published.

    A withdrawn story is archived rather than published, so it drops out here
    without anything else having to remember to exclude it. Content from a
    deactivated organisation stays visible: what a body published, it
    published, and the way to take it back is to withdraw it.
    """
    return db.query(Story).filter(Story.status == StoryStatus.PUBLISHED)


def _published_evidence(db: Session):
    """Evidence records that were published."""
    return db.query(Evidence).filter(Evidence.status == EvidenceStatus.PUBLISHED)


def _published_questions(db: Session):
    """Questions whose answers were approved and published."""
    return db.query(Question).filter(
        Question.status == QuestionStatus.PUBLISHED,
        Question.is_published.is_(True),
    )


@router.get("/stories", response_model=dict)
@limiter.limit(PUBLIC_READ_LIMIT)
async def list_public_stories(
    request: Request,
    language: Optional[str] = Query(None, max_length=5),
    featured_only: bool = Query(False),
    organisation_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Published stories, most recent first."""
    query = _published_stories(db)

    if language:
        query = query.filter(Story.language == language)
    if featured_only:
        query = query.filter(Story.featured.is_(True))
    if organisation_id:
        query = query.filter(Story.organisation_id == organisation_id)

    total = query.count()
    stories = (
        query.order_by(Story.published_date.desc().nullslast()).offset(skip).limit(limit).all()
    )

    return _page(total, skip, limit, [_story(story) for story in stories])


@router.get("/stories/{story_id}", response_model=PublicStory)
@limiter.limit(PUBLIC_READ_LIMIT)
async def get_public_story(
    request: Request,
    story_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """One published story."""
    story = _published_stories(db).filter(Story.id == story_id).first()
    if story is None:
        # An unpublished story is reported as missing rather than forbidden:
        # the portal must not confirm that a draft exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    return _story(story)


@router.get("/evidence", response_model=dict)
@limiter.limit(PUBLIC_READ_LIMIT)
async def list_public_evidence(
    request: Request,
    organisation_id: Optional[uuid.UUID] = Query(None),
    thematic_area_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """The public evidence register."""
    query = _published_evidence(db)

    if organisation_id:
        query = query.filter(Evidence.organisation_id == organisation_id)
    if thematic_area_id:
        query = query.filter(Evidence.thematic_area_id == thematic_area_id)

    total = query.count()
    records = (
        query.order_by(Evidence.evidence_date.desc().nullslast()).offset(skip).limit(limit).all()
    )

    return _page(total, skip, limit, [_evidence(record) for record in records])


@router.get("/evidence/{reference}", response_model=PublicEvidence)
@limiter.limit(PUBLIC_READ_LIMIT)
async def get_public_evidence(
    request: Request,
    reference: str,
    db: Session = Depends(get_db),
):
    """One published evidence record, by the reference it is cited by.

    Addressed by reference rather than id because the reference is what
    appears in a story, a report or a citation, and it never changes.
    """
    record = _published_evidence(db).filter(Evidence.reference == reference).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return _evidence(record)


@router.get("/questions", response_model=dict)
@limiter.limit(PUBLIC_READ_LIMIT)
async def list_public_questions(
    request: Request,
    language: Optional[str] = Query(None, max_length=5),
    organisation_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Questions the public asked, with the answers that were published."""
    query = _published_questions(db)

    if language:
        query = query.filter(Question.language == language)
    if organisation_id:
        query = query.filter(Question.organisation_id == organisation_id)

    total = query.count()
    questions = (
        query.order_by(Question.response_date.desc().nullslast()).offset(skip).limit(limit).all()
    )

    return _page(total, skip, limit, [_question(question) for question in questions])


@router.get("/questions/{question_id}", response_model=PublicQuestion)
@limiter.limit(PUBLIC_READ_LIMIT)
async def get_public_question(
    request: Request,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """One published question and its answer."""
    question = _published_questions(db).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return _question(question)


@router.get("/search", response_model=dict)
@limiter.limit(PUBLIC_READ_LIMIT)
async def public_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    language: Optional[str] = Query(None, max_length=5),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Search published content only.

    Runs against the same indexes as the internal search, over a set
    restricted to what has been published, so nothing under review can be
    discovered by guessing at search terms.
    """
    empty: Dict[str, Any] = {"stories": [], "evidence": [], "questions": [], "total": 0}

    tsquery = build_tsquery(q)
    if tsquery is None:
        return empty

    story_query = _published_stories(db).filter(Story.search_vector.op("@@")(tsquery))
    question_query = _published_questions(db).filter(Question.search_vector.op("@@")(tsquery))
    if language:
        story_query = story_query.filter(Story.language == language)
        question_query = question_query.filter(Question.language == language)

    stories = (
        story_query.order_by(func.ts_rank_cd(Story.search_vector, tsquery).desc())
        .limit(limit)
        .all()
    )
    records = (
        _published_evidence(db)
        .filter(Evidence.search_vector.op("@@")(tsquery))
        .order_by(func.ts_rank_cd(Evidence.search_vector, tsquery).desc())
        .limit(limit)
        .all()
    )
    questions = (
        question_query.order_by(func.ts_rank_cd(Question.search_vector, tsquery).desc())
        .limit(limit)
        .all()
    )

    return {
        "stories": [_story(story).model_dump(mode="json") for story in stories],
        "evidence": [_evidence(record).model_dump(mode="json") for record in records],
        "questions": [_question(question).model_dump(mode="json") for question in questions],
        "total": len(stories) + len(records) + len(questions),
    }


@router.get("/organisations", response_model=List[PublicOrganisation])
@limiter.limit(PUBLIC_READ_LIMIT)
async def list_public_organisations(
    request: Request,
    db: Session = Depends(get_db),
):
    """The bodies that have published something.

    Derived from published content rather than listing every tenant: the
    portal should not enumerate organisations that have chosen to publish
    nothing.
    """
    published_owners = (
        select(Story.organisation_id)
        .where(Story.status == StoryStatus.PUBLISHED)
        .union(
            select(Evidence.organisation_id).where(Evidence.status == EvidenceStatus.PUBLISHED),
            select(Question.organisation_id).where(Question.status == QuestionStatus.PUBLISHED),
        )
    )

    organisations = (
        db.query(Organisation)
        .filter(Organisation.id.in_(published_owners))
        .order_by(Organisation.name)
        .all()
    )

    return [PublicOrganisation.model_validate(org) for org in organisations]
