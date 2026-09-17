"""Administrative hierarchy logic."""

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Geography, GeographyLevel, geography_level_rank


def resolve_parent(
    db: Session, level: GeographyLevel, parent_id: Optional[uuid.UUID]
) -> Optional[Geography]:
    """Validate the proposed parent for a node at ``level``.

    A parent must sit strictly above the child in the hierarchy. Levels may be
    skipped, because not every country has every tier, but a node can never be
    placed under something at or below its own level: that would make roll-ups
    meaningless and could create a cycle.
    """
    if parent_id is None:
        if level is not GeographyLevel.COUNTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only a country may be created without a parent",
            )
        return None

    parent = db.get(Geography, parent_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent area not found",
        )

    if geography_level_rank(parent.level) >= geography_level_rank(level):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A {level.value} cannot sit under a {parent.level.value}: "
                "a parent must be higher in the hierarchy"
            ),
        )

    return parent


def descendant_ids(db: Session, root_id: uuid.UUID) -> List[uuid.UUID]:
    """Every area at or beneath ``root_id``.

    Used to answer "everything in this state" without the caller needing to
    know how deep the tree goes below it.
    """
    base = select(Geography.id).where(Geography.id == root_id).cte("subtree", recursive=True)
    base = base.union_all(
        select(Geography.id).where(Geography.parent_id == base.c.id),
    )
    return list(db.execute(select(base.c.id)).scalars())


def ancestors(db: Session, node_id: uuid.UUID) -> List[Geography]:
    """The chain from a node up to its country, nearest parent first."""
    chain: List[Geography] = []
    seen: set[uuid.UUID] = set()

    current = db.get(Geography, node_id)
    while current is not None and current.parent_id is not None:
        if current.parent_id in seen:
            # The level rule makes cycles unreachable, but a malformed row
            # must not hang the request.
            break
        seen.add(current.parent_id)
        current = db.get(Geography, current.parent_id)
        if current is not None:
            chain.append(current)

    return chain
