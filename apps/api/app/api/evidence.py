"""Evidence management endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
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
from app.models import Evidence, Geography, Indicator, Organisation, Project, Source
from app.repositories.base import BaseRepository
from app.repositories.evidence import EvidenceRepository
from app.schemas.core import EvidenceCreate, EvidenceResponse, EvidenceUpdate
from app.services.indicator import record_measurement

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


def _check_linked_records(db: Session, organisation_id: uuid.UUID, payload: dict) -> None:
    """Reject links that point at another tenant's records or at nothing.

    Evidence is only traceable if what it points at is real and belongs to the
    same organisation.
    """
    project_id = payload.get("project_id")
    if project_id is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if project.organisation_id != organisation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project belongs to a different organisation",
            )

    indicator_id = payload.get("indicator_id")
    if indicator_id is not None:
        indicator = db.get(Indicator, indicator_id)
        if indicator is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicator not found")
        if indicator.organisation_id != organisation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Indicator belongs to a different organisation",
            )

    geography_id = payload.get("geography_id")
    if geography_id is not None and db.get(Geography, geography_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Geographic area not found"
        )


@router.post("/", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    request: Request,
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

    _check_linked_records(db, evidence_create.organisation_id, evidence_create.model_dump())

    evidence_repo = EvidenceRepository(db)
    evidence_data = evidence_create.model_dump()
    evidence_data["created_by"] = access.user.id

    evidence = evidence_repo.create(evidence_data)
    audit.record(
        db,
        action=audit.CREATED,
        entity_type="evidence",
        entity_id=evidence.id,
        user=access.user,
        organisation_id=evidence.organisation_id,
        evidence_id=evidence.id,
        new_values={"title": evidence.title},
        request=request,
    )
    return evidence


@router.put("/{evidence_id}", response_model=EvidenceResponse)
async def update_evidence(
    request: Request,
    evidence_id: uuid.UUID,
    evidence_update: EvidenceUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update evidence content."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, EVIDENCE_AUTHORS)
    organisation_id = evidence.organisation_id

    update_data = evidence_update.model_dump(exclude_unset=True)
    _check_linked_records(db, organisation_id, update_data)

    update_data["updated_by"] = access.user.id
    old_values = {field: audit.serialise(getattr(evidence, field, None)) for field in update_data}

    updated = evidence_repo.update(evidence_id, update_data)
    audit.record(
        db,
        action=audit.UPDATED,
        entity_type="evidence",
        entity_id=evidence_id,
        user=access.user,
        organisation_id=organisation_id,
        evidence_id=evidence_id,
        old_values=old_values,
        new_values={field: audit.serialise(value) for field, value in update_data.items()},
        request=request,
    )
    return updated


@router.delete("/{evidence_id}")
async def delete_evidence(
    request: Request,
    evidence_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Delete evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, EVIDENCE_MANAGERS)

    # Captured before deletion: this is the only remaining record of what was
    # removed, since the delete is not reversible.
    removed = {
        "title": evidence.title,
        "status": audit.serialise(evidence.status),
        "verification_status": evidence.verification_status,
        "approval_status": evidence.approval_status,
    }
    organisation_id = evidence.organisation_id

    evidence_repo.delete(evidence_id)
    audit.record(
        db,
        action=audit.DELETED,
        entity_type="evidence",
        entity_id=evidence_id,
        user=access.user,
        organisation_id=organisation_id,
        old_values=removed,
        request=request,
    )
    return {"message": "Evidence deleted successfully"}


@router.post("/{evidence_id}/verify", response_model=EvidenceResponse)
async def verify_evidence(
    request: Request,
    evidence_id: uuid.UUID,
    notes: str = Query(""),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Record verification of evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = _get_scoped_evidence(evidence_repo, evidence_id, access)
    access.require_role(evidence.organisation_id, EVIDENCE_VERIFIERS)
    organisation_id = evidence.organisation_id

    verified = evidence_repo.mark_verified(evidence_id, access.user.id, notes)
    audit.record(
        db,
        action=audit.VERIFIED,
        entity_type="evidence",
        entity_id=evidence_id,
        user=access.user,
        organisation_id=organisation_id,
        evidence_id=evidence_id,
        new_values={"verification_status": "verified", "notes": notes},
        request=request,
    )
    return verified


@router.post("/{evidence_id}/approve", response_model=EvidenceResponse)
async def approve_evidence(
    request: Request,
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
    organisation_id = evidence.organisation_id
    verified_by = evidence.verified_by

    approved = evidence_repo.mark_approved(evidence_id, access.user.id)

    # An indicator's current value is whatever the most recent approved
    # evidence measured, so a reported figure always traces to a record.
    moved = record_measurement(db, approved)
    if moved is not None:
        db.commit()

    audit.record(
        db,
        action=audit.APPROVED,
        entity_type="evidence",
        entity_id=evidence_id,
        user=access.user,
        organisation_id=organisation_id,
        evidence_id=evidence_id,
        new_values={
            "approval_status": "approved",
            "verified_by": audit.serialise(verified_by),
        },
        request=request,
    )
    return approved


@router.post("/{evidence_id}/publish", response_model=EvidenceResponse)
async def publish_evidence(
    request: Request,
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

    organisation_id = evidence.organisation_id
    approved_by = evidence.approved_by

    published = evidence_repo.publish(evidence_id)
    audit.record(
        db,
        action=audit.PUBLISHED,
        entity_type="evidence",
        entity_id=evidence_id,
        user=access.user,
        organisation_id=organisation_id,
        evidence_id=evidence_id,
        new_values={"status": "published", "approved_by": audit.serialise(approved_by)},
        request=request,
    )
    return published
