"""Evidence repository."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Evidence, EvidenceStatus
from app.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[Evidence]):
    """Evidence repository for database operations."""

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Evidence)

    def get_by_organisation(
        self, organisation_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Evidence], int]:
        """Get all evidence for an organisation."""
        query = self.db.query(Evidence).filter(Evidence.organisation_id == organisation_id)
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_by_status(
        self,
        organisation_id: uuid.UUID,
        status: EvidenceStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Evidence], int]:
        """Get evidence by status."""
        query = self.db.query(Evidence).filter(
            and_(
                Evidence.organisation_id == organisation_id,
                Evidence.status == status,
            )
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_by_project(
        self, project_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Evidence], int]:
        """Get evidence linked to a project."""
        query = self.db.query(Evidence).filter(Evidence.project_id == project_id)
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_by_thematic_area(
        self, thematic_area_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Evidence], int]:
        """Get evidence by thematic area."""
        query = self.db.query(Evidence).filter(Evidence.thematic_area_id == thematic_area_id)
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def search(
        self,
        organisation_id: uuid.UUID,
        query_str: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Evidence], int]:
        """Search evidence by title or description."""
        q = self.db.query(Evidence).filter(
            and_(
                Evidence.organisation_id == organisation_id,
                or_(
                    Evidence.title.ilike(f"%{query_str}%"),
                    Evidence.description.ilike(f"%{query_str}%"),
                ),
            )
        )
        total = q.count()
        items = q.offset(skip).limit(limit).all()
        return items, total

    def get_verified(
        self, organisation_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Evidence], int]:
        """Get verified evidence only."""
        query = self.db.query(Evidence).filter(
            and_(
                Evidence.organisation_id == organisation_id,
                Evidence.verification_status == "verified",
                Evidence.status == EvidenceStatus.PUBLISHED,
            )
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_pending_verification(
        self, organisation_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Evidence], int]:
        """Get evidence pending verification."""
        query = self.db.query(Evidence).filter(
            and_(
                Evidence.organisation_id == organisation_id,
                Evidence.status == EvidenceStatus.UNDER_REVIEW,
            )
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def mark_verified(
        self, evidence_id: uuid.UUID, verified_by: uuid.UUID, notes: str = ""
    ) -> Optional[Evidence]:
        """Mark evidence as verified."""
        evidence = self.get_by_id(evidence_id)
        if evidence:
            evidence.verification_status = "verified"
            evidence.status = EvidenceStatus.VERIFIED
            evidence.verified_by = verified_by
            evidence.verified_date = datetime.now(timezone.utc)
            evidence.verifier_notes = notes
            self.db.commit()
            self.db.refresh(evidence)
        return evidence

    def mark_approved(self, evidence_id: uuid.UUID, approved_by: uuid.UUID) -> Optional[Evidence]:
        """Mark evidence as approved."""
        evidence = self.get_by_id(evidence_id)
        if evidence:
            evidence.approval_status = "approved"
            evidence.approved_by = approved_by
            evidence.approved_date = datetime.now(timezone.utc)
            evidence.status = EvidenceStatus.APPROVED
            self.db.commit()
            self.db.refresh(evidence)
        return evidence

    def publish(self, evidence_id: uuid.UUID) -> Optional[Evidence]:
        """Publish evidence that has completed approval."""
        evidence = self.get_by_id(evidence_id)
        if evidence and evidence.approval_status == "approved":
            evidence.status = EvidenceStatus.PUBLISHED
            self.db.commit()
            self.db.refresh(evidence)
        return evidence
