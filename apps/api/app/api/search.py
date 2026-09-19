"""Global search endpoints."""

import uuid
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.authorization import AccessControl, get_access
from app.database import get_db
from app.schemas.core import (
    EvidenceResponse,
    FieldMissionResponse,
    IntegritySignalResponse,
    QuestionResponse,
    ScenarioResponse,
    StoryResponse,
)
from app.services import search as search_service

router = APIRouter()

# The response key each content type is returned under. Kept stable: clients
# read these names.
RESULT_KEYS = {
    search_service.EVIDENCE: "evidence",
    search_service.STORY: "stories",
    search_service.QUESTION: "questions",
    search_service.PROJECT: "projects",
    search_service.SCENARIO: "scenarios",
    search_service.INTEGRITY_SIGNAL: "integrity_signals",
    search_service.FIELD_MISSION: "field_missions",
}


def _project_summary(item: Any) -> Dict[str, Any]:
    """Projects have no response schema yet, so return the identifying fields."""
    return {
        "id": item.id,
        "name": item.name,
        "code": item.code,
        "description": item.description,
        "status": item.status.value,
    }


SERIALISERS: Dict[str, Callable[[Any], Any]] = {
    search_service.EVIDENCE: EvidenceResponse.model_validate,
    search_service.STORY: StoryResponse.model_validate,
    search_service.QUESTION: QuestionResponse.model_validate,
    search_service.PROJECT: _project_summary,
    search_service.SCENARIO: ScenarioResponse.model_validate,
    search_service.INTEGRITY_SIGNAL: IntegritySignalResponse.model_validate,
    search_service.FIELD_MISSION: FieldMissionResponse.model_validate,
}


@router.get("/")
async def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    content_type: Optional[str] = Query(
        None,
        description=(
            "evidence, story, question, project, scenario, integrity_signal " "or field_mission"
        ),
    ),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    geography_id: Optional[uuid.UUID] = Query(
        None, description="Matches the area and everything beneath it"
    ),
    thematic_area_id: Optional[uuid.UUID] = Query(None),
    source_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    organisation_id: Optional[uuid.UUID] = Query(None),
    verification_status: Optional[str] = Query(None),
    owner_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Search content the caller's organisations own.

    Results are ranked by relevance. A content type that cannot express one of
    the filters is left out of the results entirely rather than returned
    unfiltered, and ``unsearchable_types`` names the spec section 35 content
    types that have no entity yet.
    """
    empty: Dict[str, Any] = {key: [] for key in RESULT_KEYS.values()}
    empty["total"] = 0
    empty["unsearchable_types"] = list(search_service.UNBUILT_TYPES)

    organisation_ids = access.organisation_ids

    # A caller who belongs to no organisation can see nothing.
    if not organisation_ids and not access.is_platform_admin:
        return empty

    # A filter naming an organisation the caller is not in must not widen what
    # they can see; it can only narrow it.
    if (
        organisation_id is not None
        and not access.is_platform_admin
        and organisation_id not in organisation_ids
    ):
        return empty

    tsquery = search_service.build_tsquery(q)
    if tsquery is None:
        return empty

    filters = search_service.SearchFilters(
        date_from=date_from,
        date_to=date_to,
        geography_id=geography_id,
        thematic_area_id=thematic_area_id,
        source_id=source_id,
        status=status,
        organisation_id=organisation_id,
        verification_status=verification_status,
        owner_id=owner_id,
    )

    results: Dict[str, Any] = dict(empty)
    total = 0

    for type_name in search_service.requested_types(content_type):
        spec = search_service.SEARCHABLES[type_name]
        page = search_service.search_type(
            db,
            spec,
            tsquery,
            filters,
            organisation_ids,
            access.is_platform_admin,
            skip,
            limit,
        )

        serialise = SERIALISERS[type_name]
        serialised: List[Any] = [serialise(item) for item in page.items]
        results[RESULT_KEYS[type_name]] = serialised
        total += page.total

    results["total"] = total
    return results
