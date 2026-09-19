"""Idempotent reference-data seeding.

Spec section 56 requires seeds to be repeatable, idempotent and safe to run
again: every function here matches on a stable natural key and updates rather
than inserting a duplicate, so running it twice leaves the same rows.
"""

from typing import List, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models import ThematicArea

# The eight streams from spec section 9. Seeded rather than hard-coded, so an
# administrator can add a ninth without a code change.
THEMATIC_STREAMS: Sequence[Tuple[str, str, str]] = (
    (
        "economic-reform",
        "Economic Reform",
        "Fiscal policy, subsidy reform, revenue and macroeconomic stability.",
    ),
    (
        "agriculture",
        "Agriculture",
        "Food production, inputs, storage, markets and rural livelihoods.",
    ),
    (
        "infrastructure",
        "Infrastructure",
        "Roads, rail, water, housing and public works.",
    ),
    (
        "energy",
        "Energy",
        "Generation, transmission, distribution, fuels and access.",
    ),
    (
        "education-health",
        "Education & Health",
        "Schools, health facilities, workforce and service delivery.",
    ),
    (
        "industrialisation",
        "Industrialisation",
        "Manufacturing, industrial capacity, trade and enterprise.",
    ),
    (
        "security",
        "Security",
        "Public safety, policing, conflict and community security.",
    ),
    (
        "governance",
        "Governance",
        "Institutions, transparency, service delivery and accountability.",
    ),
)


def seed_thematic_areas(db: Session) -> List[ThematicArea]:
    """Create or refresh the thematic streams.

    Matched on code, which is the stable identifier evidence is filed under.
    An existing stream keeps its id so nothing that references it breaks, and
    is_active is left alone so a deliberately disabled stream is not silently
    re-enabled by a later run.
    """
    seeded: List[ThematicArea] = []

    for position, (code, name, description) in enumerate(THEMATIC_STREAMS):
        area = db.query(ThematicArea).filter(ThematicArea.code == code).one_or_none()

        if area is None:
            area = ThematicArea(code=code, name=name, description=description, order=position)
            db.add(area)
        else:
            area.name = name
            area.description = description
            area.order = position

        seeded.append(area)

    db.commit()
    for area in seeded:
        db.refresh(area)

    return seeded
