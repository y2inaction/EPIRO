"""Intelligence and dashboard endpoints (spec sections 21-22).

Every figure these endpoints serve carries the basis that produced it, and
``GET /intelligence/records`` resolves that basis back to the rows. A number a
reader cannot check is an assertion, and this platform does not make those
anywhere else.

The rules live in ``app.services.intelligence``. Three are worth restating:

**Nothing here analyses people.** Intelligence means counting the platform's
own records — what a body has evidenced, been asked and done. Spec section 4
forbids profiling, and the measures are a closed set of the platform's own
entities, so there is no dimension to group by that could become one. The
filters are a closed set for the same reason, and there is deliberately none
that narrows by a person: not the author, not the reviewer, not the assignee.
Who verified a record is on that record's own approval trail, where it is
accountability; the same fact aggregated into a league table of staff is
performance surveillance, and it is not offered here.

**A bucket too small to be anything but a person is suppressed.** Questions
come from members of the public, so a breakdown of them withholds any bucket
below the minimum cell size. A zero is still reported as zero: "nobody asked"
is not sensitive, and hiding it would make the breakdown unreadable.

**A filter a measure cannot honour is refused, never ignored.** Quietly
dropping one returns an unfiltered count under a filtered heading, which is
wrong in the one way nobody checks.

Read-only. There is no endpoint here that writes anything, which is why there
is no audit entry: nothing changes state, and the records these figures count
carry their own trails.
"""

import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.authorization import AccessControl, get_access
from app.database import get_db
from app.schemas.core import (
    BreakdownResponse,
    FigureBasis,
    FigureResponse,
    IntelligenceOverview,
)
from app.services import intelligence

router = APIRouter()

SUPPRESSION_NOTE = (
    "Counts of records submitted by members of the public are withheld where "
    f"fewer than {intelligence.MIN_CELL_SIZE} records fall in a bucket, because "
    "a bucket that small describes individuals rather than a population. A zero "
    "is reported as zero."
)

DATE_NOTE = (
    "A date range narrows on when the platform recorded something, not when "
    "the thing itself happened. For evidence those differ: a handover in June "
    "recorded in September is a September record."
)


def _filters(
    organisation_id: Optional[uuid.UUID] = Query(
        None, description="Narrow to one of the organisations you belong to"
    ),
    geography_id: Optional[uuid.UUID] = Query(
        None, description="An area and everything beneath it"
    ),
    thematic_area_id: Optional[uuid.UUID] = Query(None),
    verification_status: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    since: Optional[date] = Query(None, description="Recorded on or after this date"),
    until: Optional[date] = Query(None, description="Recorded on or before this date"),
) -> intelligence.Filters:
    """The filter set, shared by every endpoint here.

    One dependency rather than seven repeated parameters, so a filter added
    later reaches every figure at once instead of reaching some of them and
    being silently absent from the rest.
    """
    return intelligence.Filters(
        organisation_id=organisation_id,
        geography_id=geography_id,
        thematic_area_id=thematic_area_id,
        verification_status=verification_status,
        status=status,
        since=since,
        until=until,
    )


def _figure(figure: intelligence.Figure, filters: intelligence.Filters) -> FigureResponse:
    """Serialise a figure with the basis that reproduces it.

    The filters are part of that basis. A figure narrowed by a filter its
    basis did not carry would not reconcile with its own drill-down.
    """
    return FigureResponse(
        label=figure.label,
        value=figure.value,
        suppressed=figure.suppressed,
        basis=FigureBasis(
            measure=figure.basis.measure,
            dimension=figure.basis.dimension,
            value=figure.basis.value,
            **filters.as_dict(),
        ),
    )


@router.get("/overview", response_model=IntelligenceOverview)
async def get_overview(
    filters: intelligence.Filters = Depends(_filters),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Headline figures for the caller's organisations.

    Each figure carries its basis, so any number here can be handed to
    ``/intelligence/records`` and checked against the rows it counted.
    """
    figures = intelligence.overview(
        db,
        sorted(access.organisation_ids),
        access.is_platform_admin,
        filters=filters,
    )

    return IntelligenceOverview(
        figures=[_figure(f, filters) for f in figures],
        minimum_cell_size=intelligence.MIN_CELL_SIZE,
        suppression_note=SUPPRESSION_NOTE,
        excluded_measures=intelligence.dropped_measures(intelligence.HEADLINES, filters),
    )


@router.get("/unresolved", response_model=IntelligenceOverview)
async def get_unresolved(
    filters: intelligence.Filters = Depends(_filters),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """What is open: recorded, and not yet taken to a conclusion.

    The same shape as the overview, because it is the same mechanism: each
    figure is a measure and one open state, carrying the basis that resolves
    it back to the records waiting.
    """
    figures = intelligence.unresolved(
        db,
        sorted(access.organisation_ids),
        access.is_platform_admin,
        filters=filters,
    )

    return IntelligenceOverview(
        figures=[_figure(f, filters) for f in figures],
        minimum_cell_size=intelligence.MIN_CELL_SIZE,
        suppression_note=SUPPRESSION_NOTE,
        excluded_measures=intelligence.dropped_measures(intelligence.UNRESOLVED, filters),
    )


@router.get("/breakdown", response_model=BreakdownResponse)
async def get_breakdown(
    measure: str = Query(..., description="evidence, questions, projects, missions, …"),
    dimension: str = Query(..., description="A dimension the measure offers"),
    filters: intelligence.Filters = Depends(_filters),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Count a measure grouped by one of its dimensions.

    The dimension must be one the measure offers: a closed set, so a caller
    cannot group by an arbitrary column and reach a field nobody meant to
    aggregate. An unknown measure, dimension or filter is refused with the
    available ones named, because a 400 that does not say what would have
    worked is a dead end.
    """
    spec = intelligence.require_measure(measure)
    intelligence.require_dimension(spec, dimension)
    intelligence.require_filters(spec, filters)

    figures = intelligence.breakdown(
        db,
        spec,
        dimension,
        sorted(access.organisation_ids),
        access.is_platform_admin,
        filters=filters,
    )

    return BreakdownResponse(
        measure=measure,
        dimension=dimension,
        figures=[_figure(f, filters) for f in figures],
        minimum_cell_size=intelligence.MIN_CELL_SIZE,
        suppressed_buckets=sum(1 for f in figures if f.suppressed),
    )


@router.get("/records", response_model=dict)
async def get_records(
    measure: str = Query(...),
    dimension: Optional[str] = Query(None),
    value: Optional[str] = Query(None),
    filters: intelligence.Filters = Depends(_filters),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """The records behind a figure.

    This is what makes the dashboard explainable rather than asserted: hand
    back a figure's own basis and get the rows it counted. Scoped to the
    caller's organisations like everything else, so a drill-down cannot reach
    further than the figure could.

    Suppression is **not** applied here, and that is correct rather than an
    oversight: suppression stops an aggregate from describing an individual to
    someone who could not otherwise see them. A caller who may read the
    underlying records already may. The threshold protects the shape of the
    published summary, not the records from their own custodians.
    """
    spec = intelligence.require_measure(measure)
    intelligence.require_filters(spec, filters)
    basis = intelligence.Basis(measure=measure, dimension=dimension, value=value)

    organisation_ids = sorted(access.organisation_ids)
    total = intelligence.count(db, spec, basis, organisation_ids, access.is_platform_admin, filters)
    rows = intelligence.records(
        db, spec, basis, organisation_ids, access.is_platform_admin, skip, limit, filters
    )

    serialise = intelligence.serialiser_for(spec)
    data: List[Any] = [serialise(row) for row in rows]

    result: Dict[str, Any] = {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "basis": {**basis.as_dict(), **filters.as_dict()},
        "data": data,
    }
    return result


@router.get("/measures", response_model=dict)
async def list_measures(
    access: AccessControl = Depends(get_access),
):
    """What can be counted, how each measure can be broken down and filtered.

    Served rather than documented so a client can build a dashboard without
    hard-coding a list that would drift from the one the server enforces —
    including which filters a measure can honour, so a client can offer only
    those rather than discovering the rest by being refused.
    """
    return {
        "minimum_cell_size": intelligence.MIN_CELL_SIZE,
        "suppression_note": SUPPRESSION_NOTE,
        "date_note": DATE_NOTE,
        "measures": [
            {
                "name": spec.name,
                "label": spec.label,
                "dimensions": sorted(spec.dimensions),
                "filters": intelligence.supported_filters(spec),
                # Stated plainly so a client can show the reader why a bucket
                # is missing, rather than rendering an unexplained blank.
                "suppressed_below_minimum": spec.discloses_individuals,
            }
            for spec in intelligence.MEASURES.values()
        ],
    }
