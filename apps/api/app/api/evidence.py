"""Evidence management endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.repositories.evidence import EvidenceRepository
from app.repositories.base import BaseRepository
from app.models import Evidence, Organisation, Project, Source
from app.schemas.core import (
    EvidenceCreate,
    EvidenceResponse,
)
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/", response_model=dict)
async def list_evidence(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: str = Query(None),
    organisation_id: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List evidence with pagination."""
    if not organisation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organisation_id is required",
        )

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
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get evidence by ID."""
    evidence_repo = EvidenceRepository(db)
    evidence = evidence_repo.get_by_id(evidence_id)

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    return evidence


@router.post("/", response_model=EvidenceResponse)
async def create_evidence(
    evidence_create: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create new evidence."""
    # Verify organisation exists
    org_repo = BaseRepository(db, Organisation)
    if not org_repo.get_by_id(evidence_create.organisation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    # Verify source exists
    source_repo = BaseRepository(db, Source)
    if not source_repo.get_by_id(evidence_create.source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    evidence_repo = EvidenceRepository(db)
    evidence_data = evidence_create.model_dump()
    evidence_data["created_by"] = current_user.id

    evidence = evidence_repo.create(evidence_data)
    return evidence


@router.put("/{evidence_id}", response_model=EvidenceResponse)
async def update_evidence(
    evidence_id: str,
    evidence_update: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = evidence_repo.get_by_id(evidence_id)

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    evidence_update["updated_by"] = current_user.id
    updated_evidence = evidence_repo.update(evidence_id, evidence_update)

    return updated_evidence


@router.delete("/{evidence_id}")
async def delete_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete evidence."""
    evidence_repo = EvidenceRepository(db)

    if not evidence_repo.delete(evidence_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    return {"message": "Evidence deleted successfully"}


@router.post("/{evidence_id}/verify", response_model=EvidenceResponse)
async def verify_evidence(
    evidence_id: str,
    notes: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = evidence_repo.mark_verified(evidence_id, str(current_user.id), notes)

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    return evidence


@router.post("/{evidence_id}/approve", response_model=EvidenceResponse)
async def approve_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = evidence_repo.mark_approved(evidence_id, str(current_user.id))

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    return evidence


@router.post("/{evidence_id}/publish", response_model=EvidenceResponse)
async def publish_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish evidence."""
    evidence_repo = EvidenceRepository(db)
    evidence = evidence_repo.publish(evidence_id)

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found or not approved",
        )

    return evidence
