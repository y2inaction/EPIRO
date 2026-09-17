"""Evidence content rules."""

from typing import Any, Dict

from app.models import Evidence, EvidenceStatus


def invalidate_review(evidence: Evidence) -> Dict[str, Any]:
    """The workflow fields a content change must reset, plus the new version.

    An approval covers the content that was in front of the approver. Leaving a
    sign-off in place across an edit would let a record be verified, approved,
    then quietly changed and published: the approval trail would show a
    decision that never covered what went out. So an edit always raises the
    version, and an edit to a record that has cleared verification or approval
    sends it back to draft to be reviewed again.

    Returned rather than applied, so the caller can fold it into the one update
    it already commits.
    """
    changes: Dict[str, Any] = {"version": evidence.version + 1}

    reviewed = evidence.verification_status == "verified" or evidence.approval_status == "approved"
    if reviewed:
        changes.update(
            {
                "status": EvidenceStatus.DRAFT,
                "verification_status": "unverified",
                "verified_by": None,
                "verified_date": None,
                "verifier_notes": None,
                "approval_status": "pending",
                "approved_by": None,
                "approved_date": None,
            }
        )

    return changes
