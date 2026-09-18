"""Readiness rules (spec sections 28-31).

A readiness colour is the most quotable thing this platform produces. "We are
GREEN on flood response" is a claim somebody will repeat in a briefing, and
unlike a story or a correction it has no evidence attached to it by
construction. So the rule here is the one the rest of the platform applies to
everything else, in the only form it can take for a status field:

**A status may be declared as bad as you like, and no better than the record
supports.**

The floor is computed from four things the system already knows:

* whether a playbook exists at all,
* whether it has ever been rehearsed,
* whether the rehearsal is still current,
* whether anything critical the rehearsal found is still open.

An owner may declare worse than the floor — they may know a key person has
left, or a supplier has failed, and none of that is in the database. They may
not declare better, and no role is exempt. A configuration or a seniority that
let someone mark an untested scenario GREEN would make the whole matrix
worthless, in exactly the way spec section 36's final-stage rule guards
against from the other side.

Nothing here scores or ranks people. A drill finding describes what the
response could not do, never who was at fault.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence

from fastapi import HTTPException, status

from app.models import (
    READINESS_SEVERITY,
    Drill,
    DrillFinding,
    DrillStatus,
    FindingSeverity,
    ReadinessStatus,
    Scenario,
)

# A finding at this level holds readiness down until somebody else confirms it
# is closed. Below it, a gap is recorded but does not by itself cap the colour.
BLOCKING_SEVERITY = FindingSeverity.CRITICAL

# Used when a scenario has not said how often it must be rehearsed. Long
# enough not to be arbitrary, short enough that "we drilled it once in 2019"
# does not read as current.
DEFAULT_DRILL_INTERVAL_DAYS = 365


@dataclass(frozen=True)
class Floor:
    """The best status the record supports, and why it is not better."""

    status: ReadinessStatus
    reasons: List[str]

    def permits(self, declared: ReadinessStatus) -> bool:
        """Whether ``declared`` is this bad or worse."""
        return READINESS_SEVERITY[declared] >= READINESS_SEVERITY[self.status]


def last_completion(drills: Sequence[Drill]) -> Optional[datetime]:
    """When this scenario was last actually rehearsed, if it ever was.

    The completion time rather than the drill, because that is the only part
    the readiness rules need and returning it directly means no caller has to
    re-check that a "completed" drill really carries a completion time.

    A cancelled drill is deliberately not one of them. It stays on the record
    because the history of what was not rehearsed matters, but it cannot make
    a scenario look current.
    """
    completions = [
        drill.completed_at
        for drill in drills
        if drill.status is DrillStatus.COMPLETED and drill.completed_at is not None
    ]
    return max(completions) if completions else None


def open_blocking_findings(drills: Sequence[Drill]) -> List[DrillFinding]:
    """Critical findings from completed drills that nobody has closed."""
    return [
        finding
        for drill in drills
        if drill.status is DrillStatus.COMPLETED
        for finding in drill.findings
        if finding.severity is BLOCKING_SEVERITY and finding.resolved_at is None
    ]


def drill_is_current(scenario: Scenario, completed_at: Optional[datetime], today: date) -> bool:
    """Whether the most recent rehearsal still counts as current."""
    if completed_at is None:
        return False

    interval = scenario.drill_interval_days or DEFAULT_DRILL_INTERVAL_DAYS
    return completed_at.date() + timedelta(days=interval) >= today


def floor_for(scenario: Scenario, today: Optional[date] = None) -> Floor:
    """The best status this scenario's record supports.

    Each reason is phrased so that it reads as an instruction to whoever wants
    a better colour: it names the thing that is missing, not a grade.
    """
    today = today or date.today()
    reasons: List[str] = []
    worst = ReadinessStatus.GREEN

    def hold_at(level: ReadinessStatus, reason: str) -> None:
        nonlocal worst
        reasons.append(reason)
        if READINESS_SEVERITY[level] > READINESS_SEVERITY[worst]:
            worst = level

    if not scenario.playbook_steps:
        # No plan at all is the deepest hole: there is nothing to rehearse and
        # nothing for anyone to follow on the day.
        hold_at(ReadinessStatus.RED, "The scenario has no playbook steps, so there is no plan")

    drills = list(scenario.drills)
    latest = last_completion(drills)

    if latest is None:
        hold_at(
            ReadinessStatus.AMBER,
            "The scenario has never been rehearsed, so the plan is untested",
        )
    elif not drill_is_current(scenario, latest, today):
        interval = scenario.drill_interval_days or DEFAULT_DRILL_INTERVAL_DAYS
        hold_at(
            ReadinessStatus.AMBER,
            (
                f"The last rehearsal was on {latest.date().isoformat()}, "
                f"which is beyond the {interval}-day interval set for this scenario"
            ),
        )

    blocking = open_blocking_findings(drills)
    if blocking:
        count = len(blocking)
        noun = "finding" if count == 1 else "findings"
        verb = "remains" if count == 1 else "remain"
        hold_at(
            ReadinessStatus.AMBER,
            f"{count} critical {noun} from a rehearsal {verb} open",
        )

    return Floor(status=worst, reasons=reasons)


def require_declarable(
    scenario: Scenario, declared: ReadinessStatus, today: Optional[date] = None
) -> Floor:
    """Refuse a status better than the record supports.

    No role is exempt, a platform administrator included. The check exists so
    that a readiness matrix means something to whoever reads it, and a
    privilege that could switch it off would defeat it entirely — the same
    reason separation of duties is not waived for a super admin.
    """
    floor = floor_for(scenario, today)
    if floor.permits(declared):
        return floor

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"This scenario cannot be declared {declared.value}. The record "
            f"supports no better than {floor.status.value}: "
            + "; ".join(floor.reasons)
            + ". Declare a worse status, or close the gap first."
        ),
    )


def require_distinct_resolver(finding: DrillFinding, user_id: uuid.UUID) -> None:
    """Refuse to let the person who raised a finding also close it.

    Recording a finding as resolved is a confirmation that the gap is gone.
    The person who found it may well be the one who fixes it; somebody else
    has to be the one who says it is fixed.
    """
    if finding.raised_by is not None and finding.raised_by == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Separation of duties: a drill finding is confirmed resolved by "
                "someone other than the person who raised it"
            ),
        )


def require_positions_contiguous(positions: Sequence[int]) -> None:
    """Refuse a playbook whose steps do not form 1..n.

    A plan with a gap or a repeat at step 3 is ambiguous about what happens
    next, which is the one thing a plan exists to remove.
    """
    if sorted(positions) != list(range(1, len(positions) + 1)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playbook steps must be numbered 1 to n with no gaps or repeats",
        )
