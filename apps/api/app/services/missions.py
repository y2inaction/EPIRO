"""Field mission rules (spec section 18).

Three things this module exists to hold.

**A mission cannot be approved without a written risk assessment.** Sending
people somewhere is the most consequential thing the platform authorises, and
it is the one action whose cost falls on staff rather than on a record. The
requirement is structural rather than procedural: there is no path through the
API that approves a mission with the field empty.

**The person who planned a mission may not approve it.** The same separation
the platform applies to publishing information, applied to sending people out.
Somebody other than the planner has to have read the risk assessment.

**Overdue is derived, never stored.** Whether a team has missed a check-in is
computed from the last check-in and the mission's interval, the same way a
scenario's readiness floor is computed rather than cached. A stored flag would
need something to set it, and the thing that sets it is exactly what fails
when a mission goes wrong.

Nothing here tracks a person. See the FieldMission model docstring: location
is recorded at mission level, a check-in is a state rather than a position,
and the tables have nowhere to put a movement trail.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Set

from fastapi import HTTPException, status

from app.models import (
    EvidenceStatus,
    FieldMission,
    MissionCheckIn,
    MissionStatus,
    SafetyState,
)

# A mission that has not said how often it will report in. Long enough not to
# raise an alarm over a quiet afternoon, short enough that a team missing for a
# day is visible.
DEFAULT_CHECK_IN_INTERVAL_HOURS = 24

# Evidence may only be attached to a mission that is actually happening or has
# happened. Filing an observation against a trip nobody has taken yet would
# make the provenance claim false.
CAPTURABLE: Set[MissionStatus] = {MissionStatus.IN_PROGRESS, MissionStatus.COMPLETED}

# A mission that is still live in the sense that somebody should be watching
# for check-ins.
RUNNING: Set[MissionStatus] = {MissionStatus.IN_PROGRESS}


@dataclass(frozen=True)
class SafetyPosture:
    """What a coordinator needs to know about a mission right now."""

    state: SafetyState
    last_reported_at: Optional[datetime]
    overdue: bool
    # Present so a caller can say "4 hours late" rather than only "late".
    hours_since_report: Optional[float]

    @property
    def needs_attention(self) -> bool:
        """Whether somebody should be doing something about this mission."""
        return self.overdue or self.state is SafetyState.ASSISTANCE_REQUIRED


def latest_check_in(check_ins: Sequence[MissionCheckIn]) -> Optional[MissionCheckIn]:
    """The most recent report, if the team has made one."""
    if not check_ins:
        return None
    return max(check_ins, key=lambda c: c.reported_at)


def safety_posture(mission: FieldMission, now: Optional[datetime] = None) -> SafetyPosture:
    """How this mission is doing, derived rather than stored.

    A mission that is not running is never overdue: a team that has not left
    yet, or has come back, is not missing.
    """
    now = now or datetime.now(timezone.utc)
    latest = latest_check_in(list(mission.check_ins))

    if mission.status not in RUNNING:
        return SafetyPosture(
            state=latest.state if latest else SafetyState.SAFE,
            last_reported_at=latest.reported_at if latest else None,
            overdue=False,
            hours_since_report=None,
        )

    interval = mission.check_in_interval_hours or DEFAULT_CHECK_IN_INTERVAL_HOURS
    # A mission that has started and never reported is measured from its start,
    # so a team that leaves and is never heard from is overdue rather than
    # silently fine.
    since = latest.reported_at if latest else mission.started_at
    if since is None:
        return SafetyPosture(
            state=SafetyState.SAFE,
            last_reported_at=None,
            overdue=False,
            hours_since_report=None,
        )

    elapsed = now - since
    return SafetyPosture(
        state=latest.state if latest else SafetyState.SAFE,
        last_reported_at=latest.reported_at if latest else None,
        overdue=elapsed > timedelta(hours=interval),
        hours_since_report=round(elapsed.total_seconds() / 3600, 1),
    )


def require_status(mission: FieldMission, allowed: Set[MissionStatus], detail: str) -> None:
    """Refuse a transition the mission's current state does not allow."""
    if mission.status not in allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def require_risk_assessment(mission: FieldMission) -> None:
    """Refuse to approve a mission nobody has thought about.

    The one rule in this module whose cost falls on people rather than on data.
    """
    if not mission.risk_assessment or not mission.risk_assessment.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A mission cannot be approved without a written risk assessment. "
                "Record what could go wrong and what is being done about it first."
            ),
        )


def require_dates_in_order(planned_start, planned_end) -> None:
    """Refuse a mission that ends before it begins."""
    if planned_end < planned_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A mission cannot end before it starts",
        )


def require_capturable(mission: FieldMission) -> None:
    """Refuse to file evidence against a trip that has not happened."""
    if mission.status not in CAPTURABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Evidence can only be captured against a mission that is under way " "or completed"
            ),
        )


def captured_evidence_defaults(mission: FieldMission) -> dict:
    """The provenance a field capture inherits from its mission.

    Evidence captured in the field starts as a draft like any other: going and
    looking is how a record is gathered, not a reason to skip verification.
    """
    return {
        "organisation_id": mission.organisation_id,
        "field_mission_id": mission.id,
        "status": EvidenceStatus.DRAFT,
        "verification_status": "unverified",
    }


def require_distinct_approver(mission: FieldMission, user_id: uuid.UUID) -> None:
    """Refuse to let the planner approve their own mission."""
    if mission.created_by is not None and mission.created_by == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Separation of duties: a field mission is approved by someone "
                "other than the person who planned it"
            ),
        )
