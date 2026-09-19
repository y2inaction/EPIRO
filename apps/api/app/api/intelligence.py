"""Intelligence and dashboard endpoints (spec sections 21-22).

Every figure these endpoints serve carries the basis that produced it, and
``GET /intelligence/records`` resolves that basis back to the rows. A number a
reader cannot check is an assertion, and this platform does not make those
anywhere else.

The rules live in ``app.services.intelligence``. Two are worth restating:

**Nothing here analyses people.** Intelligence means counting the platform's
own records — what a body has evidenced, been asked and done. Spec section 4
forbids profiling, and the measures are a closed set of the platform's own
entities, so there is no dimension to group by that could become one.

**A bucket too small to be anything but a person is suppressed.** Questions
come from members of the public, so a breakdown of them withholds any bucket
below the minimum cell size. A zero is still reported as zero: "nobody asked"
is not sensitive, and hiding it would make the breakdown unreadable.

Read-only. There is no endpoint here that writes anything, which is why there
is no audit entry: nothing changes state, and the records these figures count
carry their own trails.
"""

import uuid
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


def _figure(figure: intelligence.Figure) -> FigureResponse:
    """Serialise a figure with the basis that reproduces it."""
    return FigureResponse(
        label=figure.label,
        value=figure.value,
        suppressed=figure.suppressed,
        basis=FigureBasis(
            measure=figure.basis.measure,
            dimension=figure.basis.dimension,
            value=figure.basis.value,
            geography_id=figure.basis.geography_id,
        ),
    )


@router.get("/overview", response_model=IntelligenceOverview)
async def get_overview(
    geography_id: Optional[uuid.UUID] = Query(
        None, description="Restrict to an area and everything beneath it"
    ),
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
        geography_id=geography_id,
    )

    return IntelligenceOverview(
        figures=[_figure(f) for f in figures],
        minimum_cell_size=intelligence.MIN_CELL_SIZE,
        suppression_note=SUPPRESSION_NOTE,
    )


@router.get("/breakdown", response_model=BreakdownResponse)
async def get_breakdown(
    measure: str = Query(..., description="evidence, questions, projects, missions, …"),
    dimension: str = Query(..., description="A dimension the measure offers"),
    geography_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    access: AccessControl = Depends(get_access),
):
    """Count a measure grouped by one of its dimensions.

    The dimension must be one the measure offers: a closed set, so a caller
    cannot group by an arbitrary column and reach a field nobody meant to
    aggregate. An unknown measure or dimension is refused with the available
    ones named, because a 400 that does not say what would have worked is a
    dead end.
    """
    spec = intelligence.require_measure(measure)
    intelligence.require_dimension(spec, dimension)

    figures = intelligence.breakdown(
        db,
        spec,
        dimension,
        sorted(access.organisation_ids),
        access.is_platform_admin,
        geography_id=geography_id,
    )

    return BreakdownResponse(
        measure=measure,
        dimension=dimension,
        figures=[_figure(f) for f in figures],
        minimum_cell_size=intelligence.MIN_CELL_SIZE,
        suppressed_buckets=sum(1 for f in figures if f.suppressed),
    )


@router.get("/records", response_model=dict)
async def get_records(
    measure: str = Query(...),
    dimension: Optional[str] = Query(None),
    value: Optional[str] = Query(None),
    geography_id: Optional[uuid.UUID] = Query(None),
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
    basis = intelligence.Basis(
        measure=measure,
        dimension=dimension,
        value=value,
        geography_id=geography_id,
    )

    organisation_ids = sorted(access.organisation_ids)
    total = intelligence.count(db, spec, basis, organisation_ids, access.is_platform_admin)
    rows = intelligence.records(
        db, spec, basis, organisation_ids, access.is_platform_admin, skip, limit
    )

    serialise = intelligence.serialiser_for(spec)
    data: List[Any] = [serialise(row) for row in rows]

    result: Dict[str, Any] = {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "basis": basis.as_dict(),
        "data": data,
    }
    return result


@router.get("/measures", response_model=dict)
async def list_measures(
    access: AccessControl = Depends(get_access),
):
    """What can be counted, and how each measure can be broken down.

    Served rather than documented so a client can build a dashboard without
    hard-coding a list that would drift from the one the server enforces.
    """
    return {
        "minimum_cell_size": intelligence.MIN_CELL_SIZE,
        "suppression_note": SUPPRESSION_NOTE,
        "measures": [
            {
                "name": spec.name,
                "label": spec.label,
                "dimensions": sorted(spec.dimensions),
                # Stated plainly so a client can show the reader why a bucket
                # is missing, rather than rendering an unexplained blank.
                "suppressed_below_minimum": spec.discloses_individuals,
            }
            for spec in intelligence.MEASURES.values()
        ],
    }
