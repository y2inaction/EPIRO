"""Story/Public information management endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
from app.authorization import (
    CONTENT_AUTHORS,
    PUBLISHERS,
    STORY_APPROVERS,
    AccessControl,
    get_access,
)
from app.database import get_db
from app.models import ApprovalDecision, Evidence, Story, StoryStatus
from app.repositories.base import BaseRepository
from app.schemas.core import (
    ApprovalDecisionRequest,
    ApprovalRecordResponse,
    RejectionRequest,
    StoryCreate,
    StoryResponse,
    StoryUpdate,
    WithdrawalRequest,
)
from app.services.approval import STORY, decisions_for, record_decision
from app.services.story import (
    REJECTABLE,
    SUBMITTABLE,
    UNDELETABLE,
    evidence_is_approved,
    invalidate_approval,
)

router = APIRouter()


def _get_scoped_story(db: Session, story_id: uuid.UUID, access: AccessControl) -> Story:
    """Load a story the caller is entitled to see."""
    story = BaseRepository(db, Story).get_by_id(story_id)
    if not story or not access.can_access(story.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    return story


def _require_status(story: Story, allowed, detail: str) -> None:
    """Refuse a transition the story's current state does not allow."""
    if story.status not in allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _require_approved_evidence(db: Session, story: Story) -> None:
    """Refuse to advance a story whose evidence has not cleared approval."""
    evidence = BaseRepository(db, Evidence).get_by_id(story.evidence_id)
    if not evidence_is_approved(evidence):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A story can only be published once its supporting evidence has been approved",
        )


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
    request: Request,
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

    story = BaseRepository(db, Story).create(story_data)
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="story",
        entity_id=story.id,
        user=access.user,
        organisation_id=story.organisation_id,
        evidence_id=story.evidence_id,
        new_values={"title": story.title, "status": story.status.value},
        request=request,
    )
    return story


@router.put("/{story_id}", response_model=StoryResponse)
async def update_story(
    request: Request,
    story_id: uuid.UUID,
    story_update: StoryUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update story content."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, CONTENT_AUTHORS)
    before = audit.snapshot(story, "status", "version")

    if story.status in UNDELETABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A published story cannot be edited. Withdraw it first, so the "
                "public record shows that what was published has been retracted."
            ),
        )

    update_data = story_update.model_dump(exclude_unset=True)
    # Raises the version, and returns a story that had already been approved to
    # draft: the approval covered the earlier words.
    update_data.update(invalidate_approval(story))
    update_data["updated_by"] = access.user.id

    organisation_id = story.organisation_id
    updated = BaseRepository(db, Story).update(story_id, update_data)

    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=before,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.delete("/{story_id}")
async def delete_story(
    request: Request,
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete a story that was never published."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)

    if story.status in UNDELETABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A story that has been published cannot be deleted. Withdraw it "
                "instead, so the record shows it was retracted."
            ),
        )

    organisation_id = story.organisation_id
    title = story.title

    BaseRepository(db, Story).delete(story_id)
    audit.record(
        db,
        action=audit.DELETED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values={"title": title},
        request=request,
    )
    return {"message": "Story deleted successfully"}


@router.post("/{story_id}/submit", response_model=StoryResponse)
async def submit_story(
    request: Request,
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Put a draft in front of a reviewer."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, CONTENT_AUTHORS)
    _require_status(story, SUBMITTABLE, "Only a draft or a rejected story can be submitted")

    previous = story.status.value
    story.status = StoryStatus.IN_REVIEW
    story.updated_by = access.user.id
    db.commit()
    db.refresh(story)

    audit.record(
        db,
        action=audit.SUBMITTED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=story.organisation_id,
        old_values={"status": previous},
        new_values={"status": StoryStatus.IN_REVIEW.value},
        request=request,
    )
    return story


@router.post("/{story_id}/approve", response_model=StoryResponse)
async def approve_story(
    request: Request,
    story_id: uuid.UUID,
    decision: ApprovalDecisionRequest | None = None,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Approve a story under review, without publishing it.

    Approval and publication are separate acts by separate people. Doing both
    in one call, as publish used to, meant no second pair of eyes ever saw a
    story between it being signed off and it going public.
    """
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, STORY_APPROVERS)
    before = audit.snapshot(story, "status")
    _require_status(story, {StoryStatus.IN_REVIEW}, "Only a story under review can be approved")

    access.require_distinct_actor(story.created_by)
    _require_approved_evidence(db, story)

    story.status = StoryStatus.APPROVED
    story.approved_by = access.user.id
    story.approved_date = datetime.now(timezone.utc)
    story.updated_by = access.user.id
    db.commit()
    db.refresh(story)

    record_decision(
        db,
        entity_type=STORY,
        entity_id=story_id,
        organisation_id=story.organisation_id,
        decision=ApprovalDecision.APPROVED,
        reviewer=access.user,
        comments=decision.comments if decision else None,
        entity_version=story.version,
    )

    audit.record(
        db,
        action=audit.APPROVED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=story.organisation_id,
        evidence_id=story.evidence_id,
        old_values=before,
        new_values={"status": StoryStatus.APPROVED.value},
        request=request,
    )
    return story


@router.post("/{story_id}/reject", response_model=StoryResponse)
async def reject_story(
    request: Request,
    story_id: uuid.UUID,
    rejection: RejectionRequest,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Send a story back, with a reason."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, STORY_APPROVERS)
    _require_status(
        story,
        REJECTABLE,
        (
            "Only a story under review or awaiting publication can be rejected. "
            "Withdraw a published story instead."
        ),
    )

    previous = story.status.value
    story.status = StoryStatus.REJECTED
    # An approval that has been overturned must not be left on the record.
    story.approved_by = None
    story.approved_date = None
    story.updated_by = access.user.id
    db.commit()
    db.refresh(story)

    record_decision(
        db,
        entity_type=STORY,
        entity_id=story_id,
        organisation_id=story.organisation_id,
        decision=(
            ApprovalDecision.CHANGES_REQUESTED
            if rejection.changes_requested
            else ApprovalDecision.REJECTED
        ),
        reviewer=access.user,
        comments=rejection.comments,
        entity_version=story.version,
    )

    audit.record(
        db,
        action=audit.REJECTED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=story.organisation_id,
        old_values={"status": previous},
        new_values={"status": StoryStatus.REJECTED.value, "comments": rejection.comments},
        request=request,
    )
    return story


@router.get("/{story_id}/approvals", response_model=list[ApprovalRecordResponse])
async def list_story_approvals(
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Every approval decision made against this story, oldest first."""
    _get_scoped_story(db, story_id, access)

    return [
        ApprovalRecordResponse.model_validate(record)
        for record in decisions_for(db, STORY, story_id)
    ]


@router.post("/{story_id}/publish", response_model=StoryResponse)
async def publish_story(
    request: Request,
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Publish an approved story."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)
    before = audit.snapshot(story, "status")
    _require_status(
        story,
        {StoryStatus.APPROVED},
        "A story must be approved before it can be published",
    )

    # The approver signed off the words; someone else releases them. Checking
    # the author as well keeps a single person from writing, approving and
    # publishing by holding two roles.
    access.require_distinct_actor(story.approved_by)
    access.require_distinct_actor(story.created_by)

    # Evidence can be withdrawn between approval and publication.
    _require_approved_evidence(db, story)

    approved_by = story.approved_by
    story.status = StoryStatus.PUBLISHED
    story.published_date = datetime.now(timezone.utc)
    story.updated_by = access.user.id
    db.commit()
    db.refresh(story)

    audit.record(
        db,
        action=audit.PUBLISHED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=story.organisation_id,
        evidence_id=story.evidence_id,
        old_values=before,
        new_values={
            "status": StoryStatus.PUBLISHED.value,
            "approved_by": audit.serialise(approved_by),
        },
        request=request,
    )
    return story


@router.post("/{story_id}/withdraw", response_model=StoryResponse)
async def withdraw_story(
    request: Request,
    story_id: uuid.UUID,
    withdrawal: WithdrawalRequest,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Retract a published story, with a reason."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)
    _require_status(story, {StoryStatus.PUBLISHED}, "Only a published story can be withdrawn")

    story.status = StoryStatus.ARCHIVED
    # A retracted story must not keep appearing on the front page.
    story.featured = False
    story.updated_by = access.user.id
    db.commit()
    db.refresh(story)

    audit.record(
        db,
        action=audit.WITHDRAWN,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=story.organisation_id,
        old_values={"status": StoryStatus.PUBLISHED.value},
        new_values={"status": StoryStatus.ARCHIVED.value, "reason": withdrawal.reason},
        request=request,
    )
    return story


@router.post("/{story_id}/feature", response_model=StoryResponse)
async def feature_story(
    request: Request,
    story_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Mark a published story as featured."""
    story = _get_scoped_story(db, story_id, access)
    access.require_role(story.organisation_id, PUBLISHERS)
    before = audit.snapshot(story, "featured")
    _require_status(story, {StoryStatus.PUBLISHED}, "Only a published story can be featured")

    story.featured = True
    story.updated_by = access.user.id
    db.commit()
    db.refresh(story)

    audit.record(
        db,
        action=audit.FEATURED,
        entity_type="story",
        entity_id=story_id,
        user=access.user,
        organisation_id=story.organisation_id,
        old_values=before,
        new_values={"featured": True},
        request=request,
    )
    return story
