"""Aggregate analysis over the platform's own records (spec sections 21-22).

"Intelligence" is the word in this specification that most needs pinning down,
because it is where profiling would arrive if it were going to. Spec section 4
forbids voter profiling, political preference inference, psychological
profiling and susceptibility scoring, and requires that all intelligence be
**explainable, source-linked and auditable**.

So intelligence here means exactly one thing: *counting the platform's own
records and being able to show which ones*. It is analysis of what a body has
evidenced, been asked and done — never analysis of people.

Two rules make that more than a claim.

**Every figure carries the basis that produced it.** A number on a dashboard
with no way to see what it counted is an unexplainable assertion, which is the
thing this platform refuses everywhere else. Each figure returns a measure and
the filters applied, and ``/intelligence/records`` resolves exactly that basis
back to the rows. The reconciliation is testable, and it is tested: for every
figure in the overview, fetching its basis returns that many records.

**A cell too small to be anything but a person is suppressed.** Breaking down
citizen-submitted questions by category and area is genuinely useful and is
also one step from identifying who asked what. Where a measure describes things
individuals submitted, a bucket below ``MIN_CELL_SIZE`` is reported as
suppressed rather than counted. This is ordinary statistical disclosure
control, and it is the difference between knowing what a community is asking
about and knowing what a person asked.

Suppressing one bucket is not enough on its own: with the overall total
available, a single withheld bucket is recoverable by subtraction. So a second
bucket goes with it — see ``suppress_complement``. A threshold that can be
subtracted away is worse than none, because it implies a protection that is
not there.

Suppression applies to questions and not to evidence or projects: those record
public works, not people, and hiding "three boreholes in this ward" would
conceal the state of public information rather than protect anybody.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import Select, Text, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models import (
    Action,
    AuditLog,
    Evidence,
    FieldMission,
    IntegritySignal,
    Project,
    Question,
    Scenario,
    User,
)
from app.services.geography import descendant_ids

# Below this, a bucket of citizen-submitted records is small enough that
# publishing it starts to describe individuals rather than a population. Five
# is the conventional floor in statistical disclosure control and is used here
# for the same reason: it is not a magic number, it is a line that has to be
# somewhere and is easier to defend when it is the usual one.
MIN_CELL_SIZE = 5

EVIDENCE = "evidence"
QUESTIONS = "questions"
PROJECTS = "projects"
MISSIONS = "missions"
INTEGRITY = "integrity_signals"
SCENARIOS = "scenarios"
ACTIONS = "actions"


@dataclass(frozen=True)
class Measure:
    """Something the platform can count, and what counting it may reveal.

    ``discloses_individuals`` is the important field. It is true where the rows
    are things members of the public submitted, and it turns on cell
    suppression for every breakdown of that measure.
    """

    name: str
    model: Any
    label: str
    discloses_individuals: bool
    # What the audit trail calls this entity, and the column that names one
    # record. Together these turn a trail of identifiers into a readable
    # account of what changed.
    entity_type: str = ""
    label_column: Optional[InstrumentedAttribute] = None
    # Dimension name to the column it groups by. A closed set: a caller cannot
    # ask for a breakdown by an arbitrary column, so a dimension can never be
    # a route to a field that was never meant to be aggregated.
    dimensions: Dict[str, InstrumentedAttribute] = field(default_factory=dict)
    geography_column: Optional[InstrumentedAttribute] = None


MEASURES: Dict[str, Measure] = {
    EVIDENCE: Measure(
        name=EVIDENCE,
        model=Evidence,
        label="Evidence records",
        entity_type="evidence",
        label_column=Evidence.title,
        # Evidence describes public works and public spending, not people.
        discloses_individuals=False,
        dimensions={
            "status": Evidence.status,
            "verification_status": Evidence.verification_status,
            "thematic_area_id": Evidence.thematic_area_id,
            "geography_id": Evidence.geography_id,
        },
        geography_column=Evidence.geography_id,
    ),
    QUESTIONS: Measure(
        name=QUESTIONS,
        model=Question,
        label="Questions from the public",
        entity_type="question",
        label_column=Question.question_text,
        # Submitted by members of the public. Every breakdown is suppressed
        # below the threshold.
        discloses_individuals=True,
        dimensions={
            "status": Question.status,
            "category": Question.category,
            "language": Question.language,
            "geography_id": Question.geography_id,
        },
        geography_column=Question.geography_id,
    ),
    PROJECTS: Measure(
        name=PROJECTS,
        model=Project,
        label="Projects",
        entity_type="project",
        label_column=Project.name,
        discloses_individuals=False,
        dimensions={
            "status": Project.status,
            "geography_id": Project.geography_id,
            "sector": Project.sector,
        },
        geography_column=Project.geography_id,
    ),
    MISSIONS: Measure(
        name=MISSIONS,
        model=FieldMission,
        label="Field missions",
        entity_type="field_mission",
        label_column=FieldMission.title,
        discloses_individuals=False,
        dimensions={
            "status": FieldMission.status,
            "geography_id": FieldMission.geography_id,
            "thematic_area_id": FieldMission.thematic_area_id,
        },
        geography_column=FieldMission.geography_id,
    ),
    INTEGRITY: Measure(
        name=INTEGRITY,
        model=IntegritySignal,
        label="Information integrity signals",
        entity_type="integrity_signal",
        label_column=IntegritySignal.claim,
        # A signal is about a circulating claim, not about whoever repeated it.
        discloses_individuals=False,
        dimensions={
            "status": IntegritySignal.status,
            "finding": IntegritySignal.finding,
            "priority": IntegritySignal.priority,
            "geography_id": IntegritySignal.geography_id,
        },
        geography_column=IntegritySignal.geography_id,
    ),
    ACTIONS: Measure(
        name=ACTIONS,
        model=Action,
        label="Actions",
        entity_type="action",
        label_column=Action.title,
        # A decision the organisation took, not a person. The dimensions are
        # about the action's state and where it came from; there is
        # deliberately none that groups by owner, because a register sliced
        # by person is a report on staff.
        discloses_individuals=False,
        dimensions={
            "status": Action.status,
            "origin_type": Action.origin_type,
            "geography_id": Action.geography_id,
            "thematic_area_id": Action.thematic_area_id,
        },
        geography_column=Action.geography_id,
    ),
    SCENARIOS: Measure(
        name=SCENARIOS,
        model=Scenario,
        label="Readiness scenarios",
        entity_type="scenario",
        label_column=Scenario.name,
        discloses_individuals=False,
        dimensions={
            "status": Scenario.status,
            "geography_id": Scenario.geography_id,
        },
        geography_column=Scenario.geography_id,
    ),
}


# The filters a caller may narrow any figure by. A closed set, for the same
# reason dimensions are: a filter resolved by name against arbitrary columns
# would be a route to every field on the model, including ones nobody meant to
# be queryable.
#
# Each name maps to the column it narrows. ``since`` and ``until`` both narrow
# ``created_at`` — see the note on Filters about which date that is.
FILTER_COLUMNS: Dict[str, str] = {
    "organisation_id": "organisation_id",
    "geography_id": "geography_id",
    "thematic_area_id": "thematic_area_id",
    "verification_status": "verification_status",
    "status": "status",
    "since": "created_at",
    "until": "created_at",
}


@dataclass(frozen=True)
class Filters:
    """How a figure was narrowed before anything was counted.

    Part of the basis rather than separate from it. A figure narrowed by a
    filter its basis did not carry would not reconcile with its own
    drill-down: the number would have counted one thing and the records
    another, which is exactly the unexplainable assertion this layer exists to
    avoid.

    **The dates narrow ``created_at``**, meaning when the platform recorded
    something, not when the thing itself happened. For evidence those differ:
    a borehole handed over in June and recorded in September is September's
    record. Using each measure's own event date instead would make the
    measures incomparable — a count of "things that happened" and a count of
    "things we learned" summed into one total — so one meaning is used
    throughout and stated rather than left to be discovered.
    """

    organisation_id: Optional[uuid.UUID] = None
    geography_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None
    verification_status: Optional[str] = None
    status: Optional[str] = None
    since: Optional[date] = None
    until: Optional[date] = None

    def active(self) -> Dict[str, Any]:
        """The filters actually set, by name."""
        return {
            name: getattr(self, name) for name in FILTER_COLUMNS if getattr(self, name) is not None
        }

    def as_dict(self) -> Dict[str, Any]:
        """The query parameters that reproduce this narrowing."""
        return {name: str(value) for name, value in self.active().items()}


def supported_filters(measure: "Measure") -> List[str]:
    """Which filters this measure can honour.

    Derived from the model rather than listed by hand, so a column added to an
    entity becomes filterable without anybody remembering to say so, and one
    removed stops being offered rather than failing at query time.
    """
    return sorted(name for name, column in FILTER_COLUMNS.items() if hasattr(measure.model, column))


def require_filters(measure: "Measure", filters: "Filters") -> None:
    """Refuse a filter the measure cannot honour.

    Refused rather than ignored, and this is the important half. Quietly
    dropping a filter returns an unfiltered count under a filtered heading —
    a number that is wrong in the one way nobody checks, because it looks
    exactly like the right one.
    """
    available = supported_filters(measure)
    for name in filters.active():
        if name not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{measure.name}' cannot be filtered by '{name}'. "
                    f"Available: {', '.join(available)}"
                ),
            )


@dataclass(frozen=True)
class Basis:
    """What a figure counted, in a form that can be resolved back to rows.

    This is the whole explainability mechanism. A figure without one is a
    number somebody has to take on trust.
    """

    measure: str
    dimension: Optional[str] = None
    value: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """The query parameters that resolve this basis back to its records."""
        params: Dict[str, Any] = {"measure": self.measure}
        if self.dimension is not None:
            params["dimension"] = self.dimension
        if self.value is not None:
            params["value"] = self.value
        return params


@dataclass(frozen=True)
class Figure:
    """One number, what it counted, and how to see the records behind it."""

    label: str
    value: Optional[int]
    basis: Basis
    # True when the count exists but is withheld because the bucket is small
    # enough to describe individuals. Distinguished from a genuine zero:
    # "nobody asked" and "too few asked to say" are different facts.
    suppressed: bool = False


def require_measure(name: str) -> Measure:
    """Look up a measure, refusing one that does not exist."""
    measure = MEASURES.get(name)
    if measure is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown measure. Available: {', '.join(sorted(MEASURES))}",
        )
    return measure


def require_dimension(measure: Measure, dimension: str) -> InstrumentedAttribute:
    """Look up a dimension on a measure, refusing one it does not offer.

    Closed rather than open: a caller cannot group by an arbitrary column, so
    no dimension can become a route to a field nobody meant to aggregate.
    """
    column = measure.dimensions.get(dimension)
    if column is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{measure.name}' cannot be broken down by '{dimension}'. "
                f"Available: {', '.join(sorted(measure.dimensions))}"
            ),
        )
    return column


def scoped(
    statement: Select,
    measure: Measure,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
) -> Select:
    """Restrict a statement to the caller's tenants."""
    if is_platform_admin:
        return statement
    return statement.where(measure.model.organisation_id.in_(organisation_ids))


def apply_filters(
    statement: Select,
    measure: Measure,
    filters: Filters,
    db: Session,
) -> Select:
    """Narrow a statement by everything the caller filtered on."""
    require_filters(measure, filters)

    if filters.organisation_id is not None:
        # Narrows within what the caller may already see; it never widens it,
        # because tenant scoping is applied separately and always.
        statement = statement.where(measure.model.organisation_id == filters.organisation_id)

    if filters.geography_id is not None:
        # "In this state" means the state and everything beneath it, matching
        # how search resolves the same filter.
        statement = statement.where(
            measure.model.geography_id.in_(descendant_ids(db, filters.geography_id))
        )

    if filters.thematic_area_id is not None:
        statement = statement.where(measure.model.thematic_area_id == filters.thematic_area_id)

    if filters.verification_status is not None:
        statement = statement.where(
            measure.model.verification_status.cast(Text) == filters.verification_status
        )

    if filters.status is not None:
        statement = statement.where(measure.model.status.cast(Text) == filters.status)

    if filters.since is not None:
        statement = statement.where(
            measure.model.created_at >= datetime.combine(filters.since, time.min)
        )

    if filters.until is not None:
        # Inclusive of the whole closing day. A reader who asks for "up to the
        # 30th" means the 30th, not midnight at the start of it, and an
        # off-by-one here silently drops a day of records.
        statement = statement.where(
            measure.model.created_at < datetime.combine(filters.until + timedelta(days=1), time.min)
        )

    return statement


def apply_basis(
    statement: Select,
    measure: Measure,
    basis: Basis,
    filters: Filters,
    db: Session,
) -> Select:
    """Narrow a statement to exactly what a figure counted."""
    if basis.dimension is not None:
        column = require_dimension(measure, basis.dimension)
        if basis.value is None or basis.value == "":
            statement = statement.where(column.is_(None))
        else:
            # Cast to text so an enum column and a string column compare the
            # same way, and an unrecognised value simply fails to match
            # rather than raising.
            statement = statement.where(column.cast(Text) == basis.value)

    return apply_filters(statement, measure, filters, db)


def count(
    db: Session,
    measure: Measure,
    basis: Basis,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    filters: Optional[Filters] = None,
) -> int:
    """How many records this basis covers."""
    statement = select(func.count()).select_from(measure.model)
    statement = scoped(statement, measure, organisation_ids, is_platform_admin)
    statement = apply_basis(statement, measure, basis, filters or Filters(), db)
    return int(db.execute(statement).scalar_one())


def disclose(measure: Measure, value: int, basis: Basis, label: str) -> Figure:
    """Report a count, suppressing a bucket small enough to be a person.

    A zero is reported as a zero: "nobody asked about this" is not sensitive
    and withholding it would make the whole breakdown unreadable. It is the
    small non-zero bucket that identifies.
    """
    if measure.discloses_individuals and 0 < value < MIN_CELL_SIZE:
        return Figure(label=label, value=None, basis=basis, suppressed=True)
    return Figure(label=label, value=value, basis=basis)


def suppress_complement(figures: List[Figure]) -> List[Figure]:
    """Withhold a second bucket so the first cannot be recovered by subtraction.

    Primary suppression on its own is defeated by arithmetic. If a breakdown
    reports 8 and 5 and withholds one bucket, and the overall total of 15 is
    available from the overview, the withheld bucket is 2 — which is exactly
    the number the suppression existed to hide.

    So when anything is suppressed, the smallest reported bucket goes too. That
    is the standard complementary suppression of statistical disclosure
    control, and it is what makes the threshold a rule rather than a gesture.

    Cost, stated plainly: it withholds a bucket that was large enough to
    publish. That is the price of the first one being genuinely hidden, and a
    suppression that can be subtracted away is worse than none, because it
    implies a protection that is not there.
    """
    if not any(f.suppressed for f in figures):
        return figures

    reported = [f for f in figures if not f.suppressed and f.value]
    if len(reported) < 2:
        # With fewer than two reported buckets there is nothing to hide behind
        # and nothing useful left to withhold; the residual is derivable
        # whatever is done here.
        return figures

    smallest = min(reported, key=lambda f: f.value or 0)
    return [
        Figure(label=f.label, value=None, basis=f.basis, suppressed=True) if f is smallest else f
        for f in figures
    ]


def breakdown(
    db: Session,
    measure: Measure,
    dimension: str,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    filters: Optional[Filters] = None,
) -> List[Figure]:
    """Count a measure grouped by one of its dimensions, largest first."""
    column = require_dimension(measure, dimension)
    narrowing = filters or Filters()

    statement = select(column, func.count()).select_from(measure.model).group_by(column)
    statement = scoped(statement, measure, organisation_ids, is_platform_admin)
    statement = apply_basis(statement, measure, Basis(measure=measure.name), narrowing, db)

    figures: List[Figure] = []
    for raw, total in db.execute(statement).all():
        value = getattr(raw, "value", raw)
        text_value = str(value) if value is not None else None
        figures.append(
            disclose(
                measure,
                int(total),
                Basis(measure=measure.name, dimension=dimension, value=text_value),
                label=text_value if text_value is not None else "(not recorded)",
            )
        )

    # Applied before sorting so the complement is chosen on the real numbers.
    figures = suppress_complement(figures)

    # Suppressed buckets sort last: they carry no number to rank by, and a
    # reader scanning the list wants the ones that say something first.
    figures.sort(key=lambda f: (f.value is None, -(f.value or 0)))
    return figures


def records(
    db: Session,
    measure: Measure,
    basis: Basis,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    skip: int,
    limit: int,
    filters: Optional[Filters] = None,
) -> List[Any]:
    """The rows behind a figure.

    This is what makes a figure explainable rather than asserted. It is the
    same basis, resolved the same way, so a caller can check any number on the
    dashboard against the records it came from.
    """
    statement = select(measure.model)
    statement = scoped(statement, measure, organisation_ids, is_platform_admin)
    statement = apply_basis(statement, measure, basis, filters or Filters(), db)
    statement = statement.order_by(measure.model.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(statement).scalars())


# Headline figures. Each is a measure plus the filter that defines it, so the
# overview is built out of the same basis mechanism as everything else rather
# than out of hand-written queries nobody can check.
HEADLINES: Sequence[tuple] = (
    ("Evidence records", EVIDENCE, None, None),
    ("Published evidence", EVIDENCE, "status", "published"),
    ("Evidence awaiting verification", EVIDENCE, "verification_status", "unverified"),
    ("Questions from the public", QUESTIONS, None, None),
    ("Questions answered publicly", QUESTIONS, "status", "published"),
    ("Projects", PROJECTS, None, None),
    ("Field missions", MISSIONS, None, None),
    ("Integrity signals", INTEGRITY, None, None),
    ("Readiness scenarios", SCENARIOS, None, None),
    ("Actions", ACTIONS, None, None),
)


# What "not finished with" means for each measure, as a single value of a
# single dimension.
#
# Single-valued deliberately. A basis expresses one equality, so every figure
# here drills down to exactly the records it counted — the same guarantee as
# everywhere else. A broader definition ("anything not published") would read
# better in a heading and could not be checked against its own rows, and a
# figure nobody can check is the thing this layer refuses to serve.
UNRESOLVED: Sequence[tuple] = (
    ("Evidence nobody has checked yet", EVIDENCE, "verification_status", "unverified"),
    ("Evidence checked and disputed", EVIDENCE, "verification_status", "disputed"),
    ("Questions nobody has claimed", QUESTIONS, "status", "new"),
    ("Questions claimed but unanswered", QUESTIONS, "status", "triaged"),
    ("Claims not yet looked at", INTEGRITY, "status", "new"),
    ("Claims looked at and unsettled", INTEGRITY, "finding", "unresolved"),
    ("Missions still in the field", MISSIONS, "status", "in_progress"),
    ("Scenarios at red", SCENARIOS, "status", "red"),
    ("Projects reported delayed", PROJECTS, "status", "delayed"),
    ("Actions proposed and not accepted", ACTIONS, "status", "proposed"),
    ("Actions accepted and not started", ACTIONS, "status", "accepted"),
    ("Actions under way", ACTIONS, "status", "in_progress"),
)


def _figures_for(
    db: Session,
    specification: Sequence[tuple],
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    filters: Filters,
) -> List[Figure]:
    """Count a list of (label, measure, dimension, value) against the filters."""
    figures: List[Figure] = []

    for label, measure_name, dimension, value in specification:
        measure = MEASURES[measure_name]

        if any(name not in supported_filters(measure) for name in filters.active()):
            # A mixed-measure list narrowed by a filter only some measures
            # carry. Refusing the whole request would make the filter useless;
            # counting the others unfiltered would be a lie. So the figure is
            # left out, and the response says which measures were dropped.
            continue

        basis = Basis(measure=measure_name, dimension=dimension, value=value)
        figures.append(
            disclose(
                measure,
                count(db, measure, basis, organisation_ids, is_platform_admin, filters),
                basis,
                label,
            )
        )

    return figures


def dropped_measures(specification: Sequence[tuple], filters: Filters) -> List[str]:
    """Measures a mixed list had to leave out, and which filter did it."""
    dropped: List[str] = []
    for _, measure_name, _, _ in specification:
        measure = MEASURES[measure_name]
        missing = [name for name in filters.active() if name not in supported_filters(measure)]
        if missing and measure_name not in dropped:
            dropped.append(measure_name)
    return dropped


def overview(
    db: Session,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    filters: Optional[Filters] = None,
) -> List[Figure]:
    """The headline figures, each carrying its own basis."""
    return _figures_for(db, HEADLINES, organisation_ids, is_platform_admin, filters or Filters())


def unresolved(
    db: Session,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    filters: Optional[Filters] = None,
) -> List[Figure]:
    """What is open: recorded, and not yet taken to a conclusion.

    Every figure here is an open state, not a volume. It answers "what is
    waiting" rather than "how much have we done", which is the question a
    dashboard is usually worst at because finished work is easier to count.
    """
    return _figures_for(db, UNRESOLVED, organisation_ids, is_platform_admin, filters or Filters())


def serialiser_for(measure: Measure) -> Callable[[Any], Any]:
    """The response schema a drill-down uses for this measure.

    Imported lazily: the schemas import the models, and the API imports both.
    """
    from app.schemas.core import (
        ActionResponse,
        EvidenceResponse,
        FieldMissionResponse,
        IntegritySignalResponse,
        QuestionResponse,
        ScenarioResponse,
    )

    return {
        ACTIONS: ActionResponse.model_validate,
        EVIDENCE: EvidenceResponse.model_validate,
        QUESTIONS: QuestionResponse.model_validate,
        MISSIONS: FieldMissionResponse.model_validate,
        INTEGRITY: IntegritySignalResponse.model_validate,
        SCENARIOS: ScenarioResponse.model_validate,
    }.get(measure.name, _project_summary)


def _project_summary(item: Any) -> Dict[str, Any]:
    """Projects have no response schema; return the identifying fields."""
    return {
        "id": item.id,
        "name": item.name,
        "code": item.code,
        "status": item.status.value,
    }


# --- Temporal intelligence -------------------------------------------------
#
# The questions a dashboard of totals cannot answer: what changed, when, where,
# which evidence caused it, and who was accountable.
#
# None of this is new data. Spec section 39 already requires every state
# transition to write an audit entry, and it does. What was missing was a way
# to read that trail as intelligence rather than as forensics — filtered the
# same way everything else here is filtered.


def _record_scope(
    db: Session,
    measure: Measure,
    filters: Filters,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
) -> Select:
    """The records a change has to be about, as a subquery of ids.

    Every record-level filter is applied here rather than to the trail, which
    is what lets "changes in Kano State" work at all: an audit entry carries
    no area of its own, only the record it describes.
    """
    from dataclasses import replace

    # The dates mean something different on a change and are applied to the
    # trail instead; see ``changes``.
    without_dates = replace(filters, since=None, until=None)

    ids = select(measure.model.id)
    ids = scoped(ids, measure, organisation_ids, is_platform_admin)
    return apply_filters(ids, measure, without_dates, db)


def _within_window(statement: Select, filters: Filters) -> Select:
    """Narrow a trail to when the changes happened.

    **This is the one place the date range means something different.**
    Everywhere else it narrows when a record was created; here it narrows when
    the change occurred, because "what changed in September" is a question
    about the change and not about the record's age. A record created in June
    and verified in September is a September change.
    """
    if filters.since is not None:
        statement = statement.where(
            AuditLog.created_at >= datetime.combine(filters.since, time.min)
        )
    if filters.until is not None:
        statement = statement.where(
            AuditLog.created_at < datetime.combine(filters.until + timedelta(days=1), time.min)
        )
    return statement


def _trail(
    db: Session,
    measure: Measure,
    filters: Filters,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    action: Optional[str],
) -> Select:
    """Audit entries about this measure's records, narrowed by the filters."""
    statement = select(AuditLog).where(
        AuditLog.entity_type == measure.entity_type,
        AuditLog.entity_id.in_(
            _record_scope(db, measure, filters, organisation_ids, is_platform_admin)
        ),
    )
    statement = _within_window(statement, filters)

    if action is not None:
        statement = statement.where(AuditLog.action == action)

    return statement


def count_changes(
    db: Session,
    measure: Measure,
    filters: Filters,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    action: Optional[str] = None,
) -> int:
    """How many changes this basis covers."""
    trail = _trail(db, measure, filters, organisation_ids, is_platform_admin, action).subquery()
    return int(db.execute(select(func.count()).select_from(trail)).scalar_one())


def changes(
    db: Session,
    measure: Measure,
    filters: Filters,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Any]:
    """What changed, most recent first."""
    statement = _trail(db, measure, filters, organisation_ids, is_platform_admin, action)
    statement = statement.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(statement).scalars())


def changes_by_action(
    db: Session,
    measure: Measure,
    filters: Filters,
    organisation_ids: Sequence[uuid.UUID],
    is_platform_admin: bool,
) -> List[Figure]:
    """What kinds of change happened, largest first.

    Grouped by action and by nothing else. Grouping the trail by the person
    who acted would turn an accountability record into a productivity report,
    and the prohibition on profiling in spec section 4 is not only about
    citizens.
    """
    trail = _trail(db, measure, filters, organisation_ids, is_platform_admin, None).subquery()
    statement = select(trail.c.action, func.count()).group_by(trail.c.action)

    figures = [
        Figure(
            label=str(action),
            value=int(total),
            # A change figure resolves back through the change feed rather
            # than the record list: the same explainability, against the trail
            # it counted.
            basis=Basis(measure=measure.name, dimension="action", value=str(action)),
        )
        for action, total in db.execute(statement).all()
    ]

    figures.sort(key=lambda f: (-(f.value or 0), f.label))
    return figures


def names_of(db: Session, user_ids: Sequence[uuid.UUID]) -> Dict[uuid.UUID, str]:
    """Who the actors on a page of changes were.

    Resolved per entry, which is accountability: spec section 39 exists so a
    reviewer can be answered for. It is deliberately **not** offered as a
    filter or a grouping, because that is the same fact turned into a league
    table of staff.
    """
    if not user_ids:
        return {}

    rows = db.execute(
        select(User.id, User.first_name, User.last_name).where(User.id.in_(set(user_ids)))
    ).all()
    return {row[0]: f"{row[1]} {row[2]}".strip() for row in rows}


def titles_of(
    db: Session, measure: Measure, record_ids: Sequence[uuid.UUID]
) -> Dict[uuid.UUID, str]:
    """What the records on a page of changes are called."""
    if not record_ids or measure.label_column is None:
        return {}

    rows = db.execute(
        select(measure.model.id, measure.label_column).where(measure.model.id.in_(set(record_ids)))
    ).all()
    return {row[0]: str(row[1]) if row[1] is not None else "" for row in rows}


def fields_changed(entry: Any) -> List[Dict[str, Any]]:
    """Which fields moved, and from what to what.

    The audit trail stores whole snapshots. A reader wants the difference, and
    computing it here rather than in the client means every client gets the
    same answer.

    ``had_previous`` exists because of a real gap rather than a hypothetical
    one. The transition endpoints record what a record *became* and not what
    it was, so for those entries the prior value is **unrecorded**, which is a
    different fact from the prior value having been empty. Reporting the
    absent key as ``null`` made the feed say "verification status: not set →
    verified" about a record that had been sitting at "unverified" — an
    assertion the trail never made. See docs/STATUS.md.
    """
    old = entry.old_values or {}
    new = entry.new_values or {}

    # Driven by what the change *asserts* it changed. A field present only in
    # the prior snapshot is context the endpoint captured, not something that
    # moved: reporting it would say "status: draft → not set" about a
    # verification that never touched the status, which is a worse lie than
    # the one this method was added to fix.
    return [
        {
            "field": key,
            "from": old.get(key),
            "to": new.get(key),
            "had_previous": key in old,
        }
        for key in sorted(new)
        if not (key in old and old.get(key) == new.get(key))
    ]
