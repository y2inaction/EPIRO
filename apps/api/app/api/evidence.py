"""Evidence management endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.authorization import (
    APPROVERS,
    EVIDENCE_AUTHORS,
    EVIDENCE_MANAGERS,
    EVIDENCE_VERIFIERS,
    PUBLISHERS,
    AccessControl,
    get_access,
)
from app.database import get_db
from app.models import Evidence, Organisation, Source
from app.repositories.base import BaseRepository
from app.repositories.evidence import EvidenceRepository
from app.schemas.core import EvidenceCreate, EvidenceResponse, EvidenceUpdate

router = APIRouter()


def _get_scoped_evidence(
    evidence_repo: EvidenceRepository,
    evidence_id: uuid.UUID,
    access: AccessControl,
) -> Evidence:
    """Load evidence the caller is entitled to see.

    A record outside the caller's organisations is reported as missing so the
    endpoint does not confirm that an id exists in another tenant.
    """
    evidence = evidence_repo.get_by_id(evidence_id)
    if not evidence or not access.can_access(evidence.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )
    return evidence


@router.get("/", response_model=dict)
async def list_evidence(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    evidence_status: Optional[str] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List evidence for an organisation the caller belongs to."""
    if not organisation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organisation_id is required",
        )

    access.require_member(organisation_id)

    evidence_repo = EvidenceRepository(db)
    items, total = evidence_repo.get_by_organisation(organisation_id, skip, limit)

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [EvidenceResponse.model_validate(item) for item in items],
    }


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get evidence by ID."""
    return _get_scoped_evidence(EvidenceRepository(db), evidence_id, access)


@router.post("/", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    evidence_create: EvidenceCreate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Create new evidence."""
    access.require_role(evidence_create.organisation_id, EVIDENCE_AUTHORS)

    org_repo = BaseRepository(db, Organisation)
    if not org_repo.get_by_id(evidence_create.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    source_repo = BaseRepository(db, Source)
    source = source_repo.get_by_id(evidence_create.source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    # A source from another tenant must not become the provenance of this
    # organisation's evidence.
    if source.organisation_id != evidence_create.organisation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source belongs to a different organisation",
        )

    evidence_repo = EvidenceRepository(db)
    evidence_data = evidence_create.model_dump()
    evidence_data["created_by"] = access.user.id

    return evidence_repo.create(evidence_data)


@router.put("/{evidence_id}", response_model=EvidenceResponse)
async def update_evidence(
    evidence_id: uuid.UUID,
    evidence_update: EvidenceUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update evidence content."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, EVIDENCE_AUTHORS)

    update_data = evidence_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id

    return evidence_repo.update(evidence_id, update_data)


@router.delete("/{evidence_id}")
async def delete_evidence(
    evidence_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, EVIDENCE_MANAGERS)

    evidence_repo.delete(evidence_id)
    return {"message": "Evidence deleted successfully"}


@router.post("/{evidence_id}/verify", response_model=EvidenceResponse)
async def verify_evidence(
    evidence_id: uuid.UUID,
    notes: str = Query(""),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Record verification of evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, EVIDENCE_VERIFIERS)

    return evidence_repo.mark_verified(evidence_id, access.user.id, notes)


@router.post("/{evidence_id}/approve", response_model=EvidenceResponse)
async def approve_evidence(
    evidence_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Approve verified evidence for publication."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, APPROVERS)

    if evidence.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence must be verified before it can be approved",
        )

    access.require_distinct_actor(evidence.verified_by)

    return evidence_repo.mark_approved(evidence_id, access.user.id)


@router.post("/{evidence_id}/publish", response_model=EvidenceResponse)
async def publish_evidence(
    evidence_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Publish approved evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, PUBLISHERS)

    if evidence.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence must be approved before it can be published",
        )

    return evidence_repo.publish(evidence_id)
