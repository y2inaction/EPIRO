"""Story/Public information management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Evidence, Story, User
from app.repositories.base import BaseRepository
from app.schemas.core import StoryCreate, StoryResponse

router = APIRouter()


@router.get("/", response_model=dict)
async def list_stories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    language: str = Query("en"),
    featured_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List stories with filters."""
    story_repo = BaseRepository(db, Story)

    # Build filter kwargs
    filters = {"language": language}
    if featured_only:
        filters["featured"] = True

    query = db.query(Story)
    for key, value in filters.items():
        if hasattr(Story, key):
            query = query.filter(getattr(Story, key) == value)

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
    story_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get story by ID."""
    story_repo = BaseRepository(db, Story)
    story = story_repo.get_by_id(story_id)

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    return story


@router.post("/", response_model=StoryResponse)
async def create_story(
    story_create: StoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new story from evidence."""
    # Verify evidence exists
    evidence_repo = BaseRepository(db, Evidence)
    if not evidence_repo.get_by_id(story_create.evidence_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    story_repo = BaseRepository(db, Story)
    story_data = story_create.model_dump()
    story_data["created_by"] = current_user.id

    story = story_repo.create(story_data)
    return story


@router.put("/{story_id}", response_model=StoryResponse)
async def update_story(
    story_id: str,
    story_update: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update story."""
    story_repo = BaseRepository(db, Story)
    story = story_repo.get_by_id(story_id)

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    story_update["updated_by"] = current_user.id
    updated_story = story_repo.update(story_id, story_update)

    return updated_story


@router.delete("/{story_id}")
async def delete_story(
    story_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete story."""
    story_repo = BaseRepository(db, Story)

    if not story_repo.delete(story_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    return {"message": "Story deleted successfully"}


@router.post("/{story_id}/publish", response_model=StoryResponse)
async def publish_story(
    story_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish story to public."""
    story_repo = BaseRepository(db, Story)
    story = story_repo.get_by_id(story_id)

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    # Update story status
    story.status = "published"
    story.updated_by = current_user.id
    db.commit()
    db.refresh(story)

    return story


@router.post("/{story_id}/feature", response_model=StoryResponse)
async def feature_story(
    story_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark story as featured."""
    story_repo = BaseRepository(db, Story)
    story = story_repo.get_by_id(story_id)

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    story.featured = True
    story.updated_by = current_user.id
    db.commit()
    db.refresh(story)

    return story
