"""Approval trail."""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import ApprovalDecision, ApprovalRecord, User

EVIDENCE = "evidence"
STORY = "story"
QUESTION = "question"
INTEGRITY_SIGNAL = "integrity_signal"


def record_decision(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    organisation_id: uuid.UUID,
    decision: ApprovalDecision,
    reviewer: User,
    comments: Optional[str] = None,
    entity_version: Optional[int] = None,
    workflow_stage_id: Optional[uuid.UUID] = None,
) -> ApprovalRecord:
    """Append a decision to the approval trail.

    Every outcome is kept, including rejections, so the record shows what was
    turned down and why rather than only what eventually went through.

    ``workflow_stage_id`` names the configured stage the decision cleared,
    where the organisation has defined a workflow. How far a record has got is
    read back from these entries rather than tracked separately; see
    app/services/workflow.py.
    """
    record = ApprovalRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        organisation_id=organisation_id,
        decision=decision,
        reviewer_id=reviewer.id,
        comments=comments,
        entity_version=entity_version,
        workflow_stage_id=workflow_stage_id,
        created_by=reviewer.id,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def decisions_for(db: Session, entity_type: str, entity_id: uuid.UUID) -> List[ApprovalRecord]:
    """Every decision recorded against one record, oldest first."""
    return (
        db.query(ApprovalRecord)
        .filter(
            ApprovalRecord.entity_type == entity_type,
            ApprovalRecord.entity_id == entity_id,
        )
        .order_by(ApprovalRecord.decided_at)
        .all()
    )
