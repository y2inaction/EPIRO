"""The decision register: what the organisation is doing about what it knows.

The specification draws a chain — evidence becomes a signal, a signal is
assessed into a finding, the finding implies something for readiness, and that
implication becomes an action somebody owns. Everything up to the finding was
already built. This is the last link, and it is the one that decides whether
the rest of the platform is accountability or just record-keeping.

Three rules are enforced here rather than left to good practice, because in
each case the alternative is a register that looks like accountability without
being it.

**An action must cite what prompted it**, and the cited record must exist and
belong to the same organisation. A register of actions nobody can trace back
to a finding is a wish list.

**Finishing or dropping an action requires a written outcome.** The status is
not the interesting part; what happened is. A record that moved to "done" with
no account of what was done explains nothing to the person who reads it in six
months.

**Deciding not to act is a recordable outcome**, not a deletion. ``dropped``
keeps the decision and the reasoning; deleting the row would keep neither, and
the reason for not acting is usually the part worth having.

**Closing is not self-certification.** The owner does the work; somebody else
records it as done or dropped. "I did the thing I said I would do and I say I
did it" is exactly the self-certification the rest of the platform refuses —
a drill finding cannot be resolved by whoever raised it, a verifier cannot
approve their own verification, an approver cannot publish what they
approved. An action register exempt from that floor would be the one place
the platform takes somebody's word for it.

The cost is real and worth stating: a body with one person on the register
cannot close anything. That is the same cost every other workflow here
already charges, and it is charged for the same reason.

There is deliberately no computed priority. Ranking what matters is a
judgement an accountable person makes, and a number generated for it would
launder that judgement into arithmetic nobody can argue with.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional, Sequence

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.models import (
    Action,
    ActionOrigin,
    ActionStatus,
    DrillFinding,
    Evidence,
    IntegritySignal,
    Scenario,
)

# What an action can be raised from, and the table each name refers to. A
# closed set: the origin is how an action is traced back to the intelligence
# that prompted it, so it cannot be an arbitrary identifier the caller
# invents.
ORIGIN_MODELS: Dict[ActionOrigin, Any] = {
    ActionOrigin.INTEGRITY_SIGNAL: IntegritySignal,
    ActionOrigin.DRILL_FINDING: DrillFinding,
    ActionOrigin.SCENARIO: Scenario,
    ActionOrigin.EVIDENCE: Evidence,
}

# Nothing further happens to an action in these states. They are the two ways
# a decision ends: it was carried out, or it was decided against.
CLOSED = {ActionStatus.DONE, ActionStatus.DROPPED}

# An action is only "being worked on" in these. Used by the overdue rule,
# which deliberately does not chase a closed action past its date.
OPEN = {ActionStatus.PROPOSED, ActionStatus.ACCEPTED, ActionStatus.IN_PROGRESS}


def require_origin(
    db: Session,
    origin_type: ActionOrigin,
    origin_id: uuid.UUID,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
) -> None:
    """Refuse an action whose stated origin does not exist, or is not yours.

    Checked rather than trusted. An origin that points at nothing would make
    the citation decorative, and one that points into another organisation
    would let a caller confirm a record exists there by watching which
    identifiers are accepted.
    """
    model = ORIGIN_MODELS[origin_type]
    record = db.query(model).filter(model.id == origin_id).first()

    if record is not None and not is_platform_admin:
        # DrillFinding reaches its organisation through the drill it belongs
        # to; everything else carries one directly.
        owner = getattr(record, "organisation_id", None)
        if owner is None and hasattr(record, "drill"):
            owner = record.drill.scenario.organisation_id if record.drill else None
        if owner not in organisation_ids:
            record = None

    if record is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No {origin_type.value.replace('_', ' ')} with that id in your "
                "organisations. An action has to cite something that exists, "
                "or the citation means nothing."
            ),
        )


def require_outcome(outcome: Optional[str]) -> str:
    """Refuse to close an action with no account of what happened."""
    if outcome is None or not outcome.strip():
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                "Write what happened before closing this. A status that "
                "changed with no account of why explains nothing later."
            ),
        )
    return outcome.strip()


def require_open(action: Action) -> None:
    """Refuse to move an action that has already been closed.

    Reopening is not offered. A decision that was carried out and then had to
    be revisited is a new decision, with its own reasoning and its own trail;
    editing the old one over the top would lose the fact that it happened
    twice.
    """
    if action.status in CLOSED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"This action was already {action.status.value}. Raise a new "
                "action rather than reopening a closed one, so both decisions "
                "keep their reasoning."
            ),
        )


def require_transition(action: Action, to: ActionStatus) -> None:
    """Refuse a move the lifecycle does not allow."""
    require_open(action)

    allowed = {
        ActionStatus.PROPOSED: {ActionStatus.ACCEPTED, ActionStatus.DROPPED},
        ActionStatus.ACCEPTED: {ActionStatus.IN_PROGRESS, ActionStatus.DROPPED},
        ActionStatus.IN_PROGRESS: {ActionStatus.DONE, ActionStatus.DROPPED},
    }[action.status]

    if to not in allowed:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"An action that is {action.status.value} cannot go straight to "
                f"{to.value}. Allowed from here: "
                f"{', '.join(sorted(s.value for s in allowed))}."
            ),
        )


def is_overdue(action: Action, today: Optional[date] = None) -> bool:
    """Whether an action is past its date and still open.

    Derived, never stored. A stored flag would be wrong from the moment the
    clock passed it until something happened to update it, and the thing most
    likely never to happen to a neglected action is an update.
    """
    if action.due_date is None or action.status not in OPEN:
        return False
    return action.due_date < (today or datetime.now(timezone.utc).date())
