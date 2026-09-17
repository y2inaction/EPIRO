"""Unified search across the content types that exist today.

Spec section 35 asks for one search over evidence, projects, documents,
stories, questions, stakeholders, field missions, intelligence, media,
scenarios and tasks, filtered by date, geography, theme, source, status,
organisation, verification and owner.

CONFIRMED here: evidence, projects, stories, questions and scenarios, with all
eight filters. The remaining content types are not searchable because the
entities do not exist yet — see ``UNBUILT_TYPES``. They are listed rather than
silently omitted so the gap is visible from the code.

Matching is Postgres full text against a stored, generated tsvector with a GIN
index, ranked by ts_rank_cd. The previous implementation used
``ILIKE '%term%'``, which no index can serve: every search was a sequential
scan of the whole table, and no amount of data would have made that acceptable.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Collection, Dict, List, Optional

from sqlalchemy import ColumnElement, Select, Text, cast, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models import (
    SEARCH_CONFIG,
    Evidence,
    Project,
    Question,
    Scenario,
    Story,
)
from app.services.geography import descendant_ids

# Spec section 35 names these too. They have no entity yet, so a search cannot
# cover them; saying so here is the difference between a known gap and a
# silently incomplete result.
UNBUILT_TYPES = ("documents", "stakeholders", "field_missions", "intelligence", "media", "tasks")

EVIDENCE = "evidence"
PROJECT = "project"
STORY = "story"
QUESTION = "question"
SCENARIO = "scenario"

# Input that is nothing but words and digits is treated as type-ahead: the
# last word matches as a prefix, so "hous" finds "housing". Anything else is
# handed to websearch_to_tsquery, which understands quoted phrases, OR and a
# leading minus for exclusion.
_SIMPLE_QUERY = re.compile(r"^[\w\s]+$", re.UNICODE)


@dataclass(frozen=True)
class Searchable:
    """How one content type answers a search.

    A column left as None means the type cannot express that filter. It is
    then excluded from a search that uses the filter, rather than returning
    rows the filter never applied to: an unfiltered row in a filtered result
    reads as a match, and that would be a false claim about the data.
    """

    name: str
    model: Any
    date_column: Optional[InstrumentedAttribute]
    geography_column: Optional[InstrumentedAttribute]
    thematic_column: Optional[InstrumentedAttribute]
    source_column: Optional[InstrumentedAttribute]
    status_column: Optional[InstrumentedAttribute]
    verification_column: Optional[InstrumentedAttribute]
    owner_column: Optional[InstrumentedAttribute]


SEARCHABLES: Dict[str, Searchable] = {
    EVIDENCE: Searchable(
        name=EVIDENCE,
        model=Evidence,
        date_column=Evidence.evidence_date,
        geography_column=Evidence.geography_id,
        thematic_column=Evidence.thematic_area_id,
        source_column=Evidence.source_id,
        status_column=Evidence.status,
        verification_column=Evidence.verification_status,
        owner_column=Evidence.created_by,
    ),
    PROJECT: Searchable(
        name=PROJECT,
        model=Project,
        date_column=Project.start_date,
        geography_column=Project.geography_id,
        thematic_column=None,
        source_column=None,
        status_column=Project.status,
        verification_column=None,
        owner_column=Project.created_by,
    ),
    STORY: Searchable(
        name=STORY,
        model=Story,
        date_column=Story.published_date,
        geography_column=None,
        thematic_column=None,
        source_column=None,
        status_column=Story.status,
        verification_column=None,
        owner_column=Story.created_by,
    ),
    QUESTION: Searchable(
        name=QUESTION,
        model=Question,
        date_column=Question.created_at,
        geography_column=Question.geography_id,
        thematic_column=None,
        source_column=None,
        status_column=Question.status,
        verification_column=None,
        owner_column=Question.assigned_to,
    ),
    SCENARIO: Searchable(
        name=SCENARIO,
        model=Scenario,
        date_column=Scenario.last_drill_date,
        geography_column=None,
        thematic_column=None,
        source_column=None,
        status_column=Scenario.status,
        verification_column=None,
        owner_column=Scenario.owner,
    ),
}


@dataclass(frozen=True)
class SearchFilters:
    """The eight filters spec section 35 requires."""

    date_from: Optional[date] = None
    date_to: Optional[date] = None
    geography_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    organisation_id: Optional[uuid.UUID] = None
    verification_status: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None


def build_tsquery(q: str) -> Optional[ColumnElement[Any]]:
    """Parse user input into a tsquery, or None when there is nothing to match.

    The terms are always passed as bind parameters, never interpolated, so a
    query string cannot reach the SQL text. The prefix form is built only from
    input that is already known to be words and digits, which keeps it out of
    tsquery's own operator syntax as well.
    """
    cleaned = q.strip()
    if not cleaned:
        return None

    if _SIMPLE_QUERY.match(cleaned):
        terms = cleaned.split()
        if not terms:
            return None
        return func.to_tsquery(SEARCH_CONFIG, " & ".join(f"{term}:*" for term in terms))

    return func.websearch_to_tsquery(SEARCH_CONFIG, cleaned)


def _status_matches(column: InstrumentedAttribute, value: str) -> ColumnElement[bool]:
    """Compare a status filter against a column that may be an enum or a string.

    Story status is free text while the others are native enums; casting to
    text compares them the same way and keeps an unknown value from raising
    instead of simply not matching.
    """
    return cast(column, Text) == value


def applies(spec: Searchable, filters: SearchFilters) -> bool:
    """Whether this content type can honour every filter that was set."""
    required = (
        (filters.geography_id, spec.geography_column),
        (filters.thematic_area_id, spec.thematic_column),
        (filters.source_id, spec.source_column),
        (filters.status, spec.status_column),
        (filters.verification_status, spec.verification_column),
        (filters.owner_id, spec.owner_column),
    )
    if any(value is not None and column is None for value, column in required):
        return False

    if (filters.date_from is not None or filters.date_to is not None) and spec.date_column is None:
        return False

    return True


def apply_filters(
    statement: Select,
    spec: Searchable,
    filters: SearchFilters,
    db: Session,
) -> Select:
    """Narrow a statement by every filter the type can express."""
    if filters.organisation_id is not None:
        statement = statement.where(spec.model.organisation_id == filters.organisation_id)

    if spec.date_column is not None:
        if filters.date_from is not None:
            statement = statement.where(spec.date_column >= filters.date_from)
        if filters.date_to is not None:
            statement = statement.where(spec.date_column <= filters.date_to)

    if filters.geography_id is not None and spec.geography_column is not None:
        # "Everything in this state" means the state and every area beneath
        # it, not only records pinned to the state node itself.
        statement = statement.where(
            spec.geography_column.in_(descendant_ids(db, filters.geography_id))
        )

    if filters.thematic_area_id is not None and spec.thematic_column is not None:
        statement = statement.where(spec.thematic_column == filters.thematic_area_id)

    if filters.source_id is not None and spec.source_column is not None:
        statement = statement.where(spec.source_column == filters.source_id)

    if filters.status is not None and spec.status_column is not None:
        statement = statement.where(_status_matches(spec.status_column, filters.status))

    if filters.verification_status is not None and spec.verification_column is not None:
        statement = statement.where(spec.verification_column == filters.verification_status)

    if filters.owner_id is not None and spec.owner_column is not None:
        statement = statement.where(spec.owner_column == filters.owner_id)

    return statement


def scope_to_organisations(
    statement: Select,
    spec: Searchable,
    organisation_ids: Collection[uuid.UUID],
    is_platform_admin: bool,
) -> Select:
    """Restrict a statement to the caller's tenants."""
    if is_platform_admin:
        return statement
    return statement.where(spec.model.organisation_id.in_(organisation_ids))


@dataclass
class SearchPage:
    """One content type's slice of a search result."""

    total: int
    items: List[Any]


def search_type(
    db: Session,
    spec: Searchable,
    tsquery: ColumnElement[Any],
    filters: SearchFilters,
    organisation_ids: Collection[uuid.UUID],
    is_platform_admin: bool,
    skip: int,
    limit: int,
) -> SearchPage:
    """Run one content type's search, ranked best first."""
    if not applies(spec, filters):
        return SearchPage(total=0, items=[])

    match = spec.model.search_vector.op("@@")(tsquery)

    statement = select(spec.model).where(match)
    statement = scope_to_organisations(statement, spec, organisation_ids, is_platform_admin)
    statement = apply_filters(statement, spec, filters, db)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = db.execute(count_statement).scalar_one()

    # ts_rank_cd weighs term density and proximity, so a title hit outranks a
    # passing mention deep in a body. created_at breaks ties so that paging is
    # stable rather than left to the planner.
    rank = func.ts_rank_cd(spec.model.search_vector, tsquery)
    ranked = statement.order_by(rank.desc(), spec.model.created_at.desc()).offset(skip).limit(limit)

    return SearchPage(total=total, items=list(db.execute(ranked).scalars()))


def requested_types(content_type: Optional[str]) -> List[str]:
    """The content types a request covers."""
    if content_type is None:
        return list(SEARCHABLES)
    if content_type in SEARCHABLES:
        return [content_type]
    return []


__all__ = [
    "EVIDENCE",
    "PROJECT",
    "QUESTION",
    "SCENARIO",
    "STORY",
    "SEARCHABLES",
    "UNBUILT_TYPES",
    "SearchFilters",
    "SearchPage",
    "Searchable",
    "applies",
    "apply_filters",
    "build_tsquery",
    "requested_types",
    "scope_to_organisations",
    "search_type",
]
