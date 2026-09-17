"""Indicator measurement rules."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Evidence, Indicator


def record_measurement(db: Session, evidence: Optional[Evidence]) -> Optional[Indicator]:
    """Carry an approved evidence measurement onto its indicator.

    An indicator's current value is never typed in by hand: it is whatever the
    most recent approved evidence measured. That way a figure on a dashboard
    can always be traced back to the record that produced it, which is the
    point of spec section 10's RESULT block.

    Returns the indicator that moved, or None when there is nothing to apply.
    Mutates only; the caller commits.
    """
    if evidence is None or evidence.indicator_id is None or evidence.measured_value is None:
        return None

    indicator = db.get(Indicator, evidence.indicator_id)
    if indicator is None:
        return None

    # A later approval must not be overwritten by an older measurement being
    # approved after it.
    measured_on = evidence.evidence_date
    if (
        indicator.current_value is not None
        and indicator.current_value_date is not None
        and measured_on is not None
        and measured_on < indicator.current_value_date
    ):
        return None

    indicator.current_value = evidence.measured_value
    indicator.current_value_date = measured_on

    return indicator
