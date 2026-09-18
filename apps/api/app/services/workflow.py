"""Configurable review workflows (spec section 36).

An organisation defines the sequence of review stages a record must clear
before it counts as approved. Spec section 36's own example —
Draft → Review → Fact Check → Compliance → Approval → Publication — is exactly
that: every configurable step in it sits between submission and publication.

Two things are deliberately **not** configurable.

The coarse lifecycle (draft, approved, published, withdrawn) stays fixed in
code. If the public portal's "published" filter read a configurable pointer,
an organisation could change what published means to the public by editing its
own workflow. Configurability must not reach the guarantees the platform makes
to people outside it.

The separation of duties on the final stage is forced regardless of what is
configured. An organisation can add stages, name them, and choose which roles
clear them; it cannot arrange for one person to be the only pair of eyes on
something before it goes out. That is the whole point of the accountability
the platform claims, and a configuration switch that turned it off would make
the claim false.
"""

import uuid
from dataclasses import dataclass
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    ApprovalDecision,
    ApprovalRecord,
    Role,
    WorkflowDefinition,
    WorkflowStage,
)

# The content types a workflow can govern, matching the approval trail's
# entity_type values.
GOVERNABLE = ("evidence", "story", "question")

# The smallest workflow that still means anything: one stage, cleared by
# somebody other than the author. Every organisation has this until it
# defines its own, and no definition may be weaker.
MINIMUM_STAGES = 1


@dataclass(frozen=True)
class Progress:
    """Where a record has got to in its organisation's workflow."""

    # None when the organisation has configured nothing: the single implicit
    # stage applies and clearing it approves the record.
    definition: Optional[WorkflowDefinition]
    stage: Optional[WorkflowStage]
    cleared: int
    total: int

    @property
    def is_final_stage(self) -> bool:
        """True when clearing the current stage approves the record."""
        return self.cleared + 1 >= self.total

    @property
    def remaining_after_this(self) -> int:
        return max(0, self.total - self.cleared - 1)


def active_definition(
    db: Session, organisation_id: uuid.UUID, entity_type: str
) -> Optional[WorkflowDefinition]:
    """The workflow this organisation uses for this kind of content, if any."""
    return (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.organisation_id == organisation_id,
            WorkflowDefinition.entity_type == entity_type,
            WorkflowDefinition.is_active.is_(True),
        )
        .first()
    )


def decisions_since_last_setback(records: Sequence[ApprovalRecord]) -> List[ApprovalRecord]:
    """Approvals that still count, oldest first.

    A rejection or a request for changes resets progress: whatever was cleared
    before it was cleared against content that has since been sent back. Only
    the approvals after the last setback still describe where the record is.
    """
    kept: List[ApprovalRecord] = []
    for record in records:
        if record.decision is ApprovalDecision.APPROVED:
            kept.append(record)
        else:
            kept.clear()
    return kept


def progress(
    db: Session,
    *,
    organisation_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    version: Optional[int],
) -> Progress:
    """How far a record has got, derived from its approval trail.

    Derived rather than stored. A pointer on the record would be a second copy
    of something the trail already knows, and the copy is what drifts.

    Approvals recorded against an earlier version do not count. An edit raises
    the version and sends a reviewed record back to draft, so a stage cleared
    against words that have since changed was not cleared against these ones.
    """
    definition = active_definition(db, organisation_id, entity_type)

    records = (
        db.query(ApprovalRecord)
        .filter(
            ApprovalRecord.entity_type == entity_type,
            ApprovalRecord.entity_id == entity_id,
        )
        .order_by(ApprovalRecord.decided_at)
        .all()
    )

    live = decisions_since_last_setback(records)
    if version is not None:
        live = [r for r in live if r.entity_version is None or r.entity_version == version]

    if definition is None or not definition.stages:
        return Progress(definition=None, stage=None, cleared=len(live), total=MINIMUM_STAGES)

    stages = list(definition.stages)
    cleared = min(len(live), len(stages))
    stage = stages[cleared] if cleared < len(stages) else None

    return Progress(definition=definition, stage=stage, cleared=cleared, total=len(stages))


def previous_reviewer(db: Session, entity_type: str, entity_id: uuid.UUID) -> Optional[uuid.UUID]:
    """Who cleared the stage before this one, if anyone did."""
    records = (
        db.query(ApprovalRecord)
        .filter(
            ApprovalRecord.entity_type == entity_type,
            ApprovalRecord.entity_id == entity_id,
        )
        .order_by(ApprovalRecord.decided_at)
        .all()
    )
    live = decisions_since_last_setback(records)
    return live[-1].reviewer_id if live else None


def require_stage_role(stage: Optional[WorkflowStage], role: Optional[Role]) -> None:
    """Refuse a caller whose role cannot clear this stage.

    With no configured stage this says nothing: the caller's role has already
    been checked against the endpoint's own requirement, which is the implicit
    single stage.
    """
    if stage is None:
        return

    # SUPER_ADMIN carries full rights inside its own organisation, as
    # everywhere else in the platform.
    if role is Role.SUPER_ADMIN:
        return

    if role is None or role.value not in stage.required_roles:
        permitted = ", ".join(sorted(stage.required_roles))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(f"The stage '{stage.name}' is cleared by one of: {permitted}"),
        )


def validate_stages(stages: Sequence[dict]) -> None:
    """Refuse a definition that would weaken the platform's guarantees.

    An organisation may add stages, name them and choose which roles clear
    them. It may not define a workflow in which nobody reviews anything, or in
    which the last pair of eyes before publication can be the same person as
    the one before. Configurability is for adding rigour, not removing it.
    """
    if len(stages) < MINIMUM_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A workflow needs at least one review stage",
        )

    for index, stage in enumerate(stages):
        roles = stage.get("required_roles") or []
        if not roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Stage {index + 1} names no role that can clear it, "
                    "so nothing could ever pass it"
                ),
            )

        unknown = [r for r in roles if r not in {member.value for member in Role}]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown role: {', '.join(sorted(unknown))}",
            )

        if Role.PUBLIC_USER.value in roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A member of the public cannot clear a review stage",
            )

    if not stages[-1].get("requires_distinct_actor", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The final stage must require a different person from the one "
                "before it. A workflow cannot be configured so that one person "
                "is the only review before something is published."
            ),
        )
