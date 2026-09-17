"""Story/Public information management endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.authorization import CONTENT_AUTHORS, PUBLISHERS, AccessControl, get_access
from app.database import get_db
from app.models import Evidence, EvidenceStatus, Story
from app.repositories.base import BaseRepository
from app.schemas.core import StoryCreate, StoryResponse, StoryUpdate

router = APIRouter()

# A story may only go public once its evidence has cleared verification and
# approval. This is the "one fact base" guarantee: nothing is published that
# is not traceable to approved evidence.
PUBLISHABLE_EVIDENCE_STATUSES = frozenset({EvidenceStatus.APPROVED, EvidenceStatus.PUBLISHED})


def _get_scoped_story(db: Session, story_id: uuid.UUID, access: AccessControl) -> Story:
    """Load a story the caller is entitled to see."""
    story = BaseRepository(db, Story).get_by_id(story_id)
    if not story or not access.can_access(story.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    return story


@router.get("/", response_model=dict)
async def list_stories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    language: str = Query("en"),
    featured_only: bool = Query(False),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List stories within the caller's organisations."""
    query = db.query(Story).filter(Story.language == language)

    if not access.is_platform_admin:
        query = query.filter(Story.organisation_id.in_(access.organisation_ids))

    if featured_only:
        query = query.filter(Story.featured.is_(True))

    total = query.count()
    stories = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [StoryResponse.model_validate(story) for story in stories],
    }


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get story by ID."""
    return _get_scoped_story(db, story_id, access)


@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    story_create: StoryCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Create a new story from evidence."""
    evidence = BaseRepository(db, Evidence).get_by_id(story_create.evidence_id)
    if not evidence or not access.can_access(evidence.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    access.require_role(evidence.organisation_id, CONTENT_AUTHORS)

    story_data = story_create.model_dump()
    # Tenancy follows the evidence the story is built from.
    story_data["organisation_id"] = evidence.organisation_id
    story_data["created_by"] = access.user.id

    return BaseRepository(db, Story).create(story_data)


@router.put("/{story_id}", response_model=StoryResponse)
async def update_story(
    story_id: uuid.UUID,
    story_update: StoryUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update story content."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, CONTENT_AUTHORS)

    update_data = story_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id

    return BaseRepository(db, Story).update(story_id, update_data)


@router.delete("/{story_id}")
async def delete_story(
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete story."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)

    BaseRepository(db, Story).delete(story_id)
    return {"message": "Story deleted successfully"}


@router.post("/{story_id}/publish", response_model=StoryResponse)
async def publish_story(
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Publish a story, provided its evidence has been approved."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)

    evidence = BaseRepository(db, Evidence).get_by_id(story.evidence_id)
    if evidence is None or evidence.status not in PUBLISHABLE_EVIDENCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A story can only be published once its supporting evidence " "has been approved"
            ),
        )

    access.require_distinct_actor(story.created_by)

    story.status = "published"
    story.approved_by = access.user.id
    story.approved_date = datetime.now(timezone.utc)
    story.published_date = datetime.now(timezone.utc)
    story.updated_by = access.user.id

    db.commit()
    db.refresh(story)

    return story


@router.post("/{story_id}/feature", response_model=StoryResponse)
async def feature_story(
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Mark a published story as featured."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)

    if story.status != "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published story can be featured",
        )

    story.featured = True
    story.updated_by = access.user.id

    db.commit()
    db.refresh(story)

    return story
