"""Information integrity rules (spec sections 25-26).

Three things this module exists to hold in one place.

**A determination must be source-linked.** Spec section 4 requires that all
intelligence be explainable, source-linked and auditable. Saying in public that
a circulating claim is false is a statement of fact by the organisation, so it
cannot be approved unless it cites an evidence record that itself passed
approval. The one exception is a finding of ``UNRESOLVED``, which asserts
nothing about the claim and therefore has nothing to source. Without that
exception the only approvable outcome would be a verdict, which is precisely
how unverified verdicts end up on the record.

**An assessment covers the wording it was written against.** Editing the claim
raises the version and sends the record back, exactly as an edit does to
evidence. Otherwise a signal could be assessed, quietly reworded, and published
with an approval that covered different words.

**Nothing here looks at who spread anything.** There is no scoring of accounts,
no reach model, no inference about the people repeating a claim. The record is
about information; see the model docstring.
"""

from typing import Any, Dict, Optional, Set

from fastapi import HTTPException, status

from app.models import (
    Evidence,
    EvidenceStatus,
    IntegrityFinding,
    IntegritySignal,
    IntegritySignalStatus,
)

# The states an assessment may be written or rewritten in. An approved or
# published signal is reopened by rejecting or withdrawing it, not by writing
# over the finding that was signed off.
ASSESSABLE: Set[IntegritySignalStatus] = {
    IntegritySignalStatus.NEW,
    IntegritySignalStatus.ASSESSING,
    IntegritySignalStatus.ASSESSED,
}

# A finding that asserts nothing about the claim, and so has no source to link.
NO_DETERMINATION = IntegrityFinding.UNRESOLVED

# Evidence that has completed approval. Published evidence is included: it
# cleared approval on the way there.
SETTLED_EVIDENCE = {EvidenceStatus.APPROVED, EvidenceStatus.PUBLISHED}


def require_status(
    signal: IntegritySignal,
    allowed: Set[IntegritySignalStatus],
    detail: str,
) -> None:
    """Refuse a transition the signal's current state does not allow."""
    if signal.status not in allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def require_source_link(signal: IntegritySignal, evidence: Optional[Evidence]) -> None:
    """Refuse to approve a determination that rests on nothing.

    The rule the platform already applies to stories, applied to corrections:
    nothing goes out that is not traceable to approved evidence. A correction
    is a harder case than a story, not a softer one — it tells the public that
    something they have heard is wrong.
    """
    if signal.finding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The signal has no assessment to approve",
        )

    if signal.finding is NO_DETERMINATION:
        return

    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A finding of '{signal.finding.value}' must cite the evidence it "
                "rests on. Record the evidence first, or assess the claim as "
                "'unresolved' if it cannot yet be settled."
            ),
        )

    if evidence.status not in SETTLED_EVIDENCE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The cited evidence has not been approved, so the finding rests "
                "on something the organisation has not stood behind"
            ),
        )


def invalidate_assessment(signal: IntegritySignal) -> Dict[str, Any]:
    """The fields a change to the claim must reset, plus the new version.

    Returned rather than applied, so the caller folds it into the one update it
    already commits — the same shape as ``services.evidence.invalidate_review``.
    """
    changes: Dict[str, Any] = {"version": signal.version + 1}

    assessed = signal.status in {
        IntegritySignalStatus.ASSESSED,
        IntegritySignalStatus.APPROVED,
    }
    if assessed:
        changes.update(
            {
                "status": IntegritySignalStatus.ASSESSING,
                "finding": None,
                "assessment": None,
                "assessed_by": None,
                "assessed_at": None,
                "approved_by": None,
                "approved_at": None,
            }
        )

    return changes


def changes_the_claim(update: Dict[str, Any], signal: IntegritySignal) -> bool:
    """Whether an update alters what was actually assessed.

    Re-prioritising a signal or reassigning it does not invalidate a finding;
    rewording the claim does. Distinguishing the two is what stops an
    assessment being thrown away every time somebody changes the owner.
    """
    for field in ("claim", "circulation", "source"):
        if field in update and update[field] != getattr(signal, field):
            return True
    return False


def publishable_response(signal: IntegritySignal) -> None:
    """Refuse to publish a correction that says nothing."""
    if not signal.response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft the response before publishing it",
        )
