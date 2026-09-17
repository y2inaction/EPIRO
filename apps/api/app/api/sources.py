"""Source registry endpoints.

Sources are the provenance layer beneath evidence: spec section 6 says no
claim counts as verified without a source, a date, an owner and a verification
status, so this module keeps those states explicit and reviewable.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.authorization import (
    EVIDENCE_AUTHORS,
    EVIDENCE_MANAGERS,
    EVIDENCE_VERIFIERS,
    AccessControl,
    get_access,
)
from app.database import get_db
from app.models import Evidence, Source, SourceType, VerificationState
from app.repositories.base import BaseRepository
from app.schemas.core import SourceCreate, SourceResponse, SourceReview, SourceUpdate

router = APIRouter()

REVIEWED = "reviewed"


def _get_scoped_source(db: Session, source_id: uuid.UUID, access: AccessControl) -> Source:
    """Load a source the caller is entitled to see."""
    source = BaseRepository(db, Source).get_by_id(source_id)
    if source is None or not access.can_access(source.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return source


@router.get("/", response_model=dict)
async def list_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    organisation_id: Optional[uuid.UUID] = Query(None),
    source_type: Optional[SourceType] = Query(None),
    verification_state: Optional[VerificationState] = Query(None),
    due_for_review: bool = Query(False),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List sources within the caller's organisations."""
    query = db.query(Source)

    if organisation_id:
        access.require_member(organisation_id)
        query = query.filter(Source.organisation_id == organisation_id)
    elif not access.is_platform_admin:
        query = query.filter(Source.organisation_id.in_(access.organisation_ids))

    if source_type is not None:
        query = query.filter(Source.source_type == source_type)
    if verification_state is not None:
        query = query.filter(Source.verification_state == verification_state)
    if due_for_review:
        query = query.filter(Source.next_review_date <= date.today())

    total = query.count()
    sources = query.order_by(Source.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [SourceResponse.model_validate(source) for source in sources],
    }


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get one source."""
    return _get_scoped_source(db, source_id, access)


@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: Request,
    source_create: SourceCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Register a source. It starts unverified."""
    access.require_role(source_create.organisation_id, EVIDENCE_AUTHORS)

    source_data = source_create.model_dump()
    source_data["created_by"] = access.user.id

    source = BaseRepository(db, Source).create(source_data)
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="source",
        entity_id=source.id,
        user=access.user,
        organisation_id=source.organisation_id,
        new_values={"name": source.name, "source_type": source.source_type.value},
        request=request,
    )
    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    request: Request,
    source_id: uuid.UUID,
    source_update: SourceUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update a source's descriptive fields."""
    source = _get_scoped_source(db, source_id, access)
    access.require_role(source.organisation_id, EVIDENCE_AUTHORS)
    organisation_id = source.organisation_id

    update_data = source_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id
    old_values = {field: audit.serialise(getattr(source, field, None)) for field in update_data}

    # Changing what a source points at invalidates the review it was given, so
    # the assessment is reset rather than silently carried over.
    if source.verification_state is not VerificationState.UNVERIFIED and any(
        field in update_data for field in ("url", "document_url", "document_hash", "source_type")
    ):
        update_data["verification_state"] = VerificationState.UNVERIFIED
        update_data["reliability_rationale"] = (
            "Reset automatically: the source's document or type changed after review."
        )

    updated = BaseRepository(db, Source).update(source_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="source",
        entity_id=source_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.post("/{source_id}/review", response_model=SourceResponse)
async def review_source(
    request: Request,
    source_id: uuid.UUID,
    review: SourceReview,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Record a verification decision against a source.

    The rationale is mandatory: a reliability classification without a stated
    reason is the unexplained score that spec section 7 rules out.
    """
    source = _get_scoped_source(db, source_id, access)
    access.require_role(source.organisation_id, EVIDENCE_VERIFIERS)

    previous = {
        "verification_state": source.verification_state.value,
        "reliability": source.reliability.value,
    }

    source.verification_state = review.verification_state
    source.reliability = review.reliability
    source.reliability_rationale = review.rationale
    source.reviewed_by = access.user.id
    source.review_date = datetime.now(timezone.utc).date()
    source.next_review_date = review.next_review_date
    source.updated_by = access.user.id

    db.commit()
    db.refresh(source)

    audit.record(
        db,
        action=REVIEWED,
        entity_type="source",
        entity_id=source_id,
        user=access.user,
        organisation_id=source.organisation_id,
        old_values=previous,
        new_values={
            "verification_state": review.verification_state.value,
            "reliability": review.reliability.value,
            "rationale": review.rationale,
        },
        request=request,
    )
    return source


@router.delete("/{source_id}")
async def delete_source(
    request: Request,
    source_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete a source that no evidence depends on."""
    source = _get_scoped_source(db, source_id, access)
    access.require_role(source.organisation_id, EVIDENCE_MANAGERS)

    in_use = db.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.source_id == source_id)
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete a source cited by {in_use} evidence records: "
                "the citation is what makes that evidence traceable"
            ),
        )

    removed = {
        "name": source.name,
        "source_type": source.source_type.value,
        "verification_state": source.verification_state.value,
    }
    organisation_id = source.organisation_id

    db.delete(source)
    db.commit()

    audit.record(
        db,
        action=audit.DELETED,
        entity_type="source",
        entity_id=source_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=removed,
        request=request,
    )
    return {"message": "Source deleted successfully"}
