"""Editorial lifecycle rules for stories.

Spec section 36 puts review and approval between drafting and publication, and
spec section 51 forbids publishing public information without the required
approval. Both were unenforceable while publish was a single call that set the
approver and the publication date together: whoever pressed publish was the
approval.
"""

from typing import Any, Dict, FrozenSet, Optional

from app.models import Evidence, EvidenceStatus, Story, StoryStatus

# A story may only be approved or published while its evidence has itself
# cleared approval. This is the "one fact base" guarantee: nothing goes public
# that is not traceable to approved evidence.
PUBLISHABLE_EVIDENCE_STATUSES: FrozenSet[EvidenceStatus] = frozenset(
    {EvidenceStatus.APPROVED, EvidenceStatus.PUBLISHED}
)

# A draft is submitted for review; a rejected story is revised and resubmitted.
SUBMITTABLE: FrozenSet[StoryStatus] = frozenset({StoryStatus.DRAFT, StoryStatus.REJECTED})

# An approval can be withdrawn before publication as well as refused during
# review, so both states can be rejected.
REJECTABLE: FrozenSet[StoryStatus] = frozenset({StoryStatus.IN_REVIEW, StoryStatus.APPROVED})

# Once something is public it is archived rather than deleted, so the record
# shows that it was retracted rather than that it never existed.
UNDELETABLE: FrozenSet[StoryStatus] = frozenset({StoryStatus.PUBLISHED, StoryStatus.ARCHIVED})


def evidence_is_approved(evidence: Optional[Evidence]) -> bool:
    """Whether the evidence behind a story has cleared approval."""
    return evidence is not None and evidence.status in PUBLISHABLE_EVIDENCE_STATUSES


def invalidate_approval(story: Story) -> Dict[str, Any]:
    """The fields a content change must reset, plus the new version.

    An approval covers the words that were in front of the approver. Without
    this, a story could be approved, quietly rewritten and then published on an
    approval that never covered what went out — the same hole the evidence
    registry had.
    """
    changes: Dict[str, Any] = {"version": story.version + 1}

    if story.status in (StoryStatus.APPROVED, StoryStatus.IN_REVIEW):
        changes.update(
            {
                "status": StoryStatus.DRAFT,
                "approved_by": None,
                "approved_date": None,
            }
        )

    return changes
