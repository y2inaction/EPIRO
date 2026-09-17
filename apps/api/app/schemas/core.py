"""Core entity schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.core import (
    EvidenceStatus,
    GeographyLevel,
    IntegritySignalPriority,
    MilestoneStatus,
    ProjectStatus,
    QuestionStatus,
    ReadinessStatus,
)


class OrganisationBase(BaseModel):
    """Base organisation schema."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    country: str = "NG"
    timezone: str = "Africa/Lagos"
    website: Optional[str] = None


class OrganisationCreate(OrganisationBase):
    """Organisation creation schema."""


class OrganisationUpdate(BaseModel):
    """Organisation update schema.

    Deliberately narrow: identity fields such as code are not client-editable.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    timezone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class OrganisationResponse(OrganisationBase):
    """Organisation response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ThematicAreaBase(BaseModel):
    """Base thematic area schema."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class ThematicAreaResponse(ThematicAreaBase):
    """Thematic area response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool


class GeographyBase(BaseModel):
    """Base geography schema."""

    name: str = Field(..., min_length=1, max_length=160)
    level: GeographyLevel
    code: Optional[str] = Field(None, max_length=32)


class GeographyCreate(GeographyBase):
    """Geography creation schema."""

    parent_id: Optional[uuid.UUID] = None
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)


class GeographyUpdate(BaseModel):
    """Geography update schema.

    Level and parent are absent: moving a node between tiers would silently
    reinterpret every project and evidence record beneath it.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=160)
    code: Optional[str] = Field(None, max_length=32)
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    is_active: Optional[bool] = None


class GeographyResponse(GeographyBase):
    """Geography response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProgrammeBase(BaseModel):
    """Base programme schema."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    budget_currency: Optional[str] = Field(None, min_length=3, max_length=3)


class ProgrammeCreate(ProgrammeBase):
    """Programme creation schema."""

    organisation_id: uuid.UUID


class ProgrammeResponse(ProgrammeBase):
    """Programme response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    actual_completion: Optional[date] = None
    budget: Optional[Decimal] = None
    budget_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    geography_id: Optional[uuid.UUID] = None
    implementing_org: Optional[str] = Field(None, max_length=255)
    funding_source: Optional[str] = Field(None, max_length=255)
    sector: Optional[str] = Field(None, max_length=100)
    target_beneficiaries: Optional[int] = Field(None, ge=0)


class ProjectCreate(ProjectBase):
    """Project creation schema."""

    organisation_id: uuid.UUID
    programme_id: Optional[uuid.UUID] = None


class ProjectUpdate(BaseModel):
    """Project update schema.

    Status is absent: it moves through the dedicated status endpoint, which
    enforces the completion rules.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    programme_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    actual_completion: Optional[date] = None
    budget: Optional[Decimal] = None
    budget_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    geography_id: Optional[uuid.UUID] = None
    implementing_org: Optional[str] = Field(None, max_length=255)
    funding_source: Optional[str] = Field(None, max_length=255)
    sector: Optional[str] = Field(None, max_length=100)
    target_beneficiaries: Optional[int] = Field(None, ge=0)


class ProjectStatusChange(BaseModel):
    """Request to move a project to a new lifecycle state."""

    status: ProjectStatus
    actual_completion: Optional[date] = None
    note: Optional[str] = Field(None, max_length=1000)


class ProjectResponse(ProjectBase):
    """Project response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    programme_id: Optional[uuid.UUID] = None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class MilestoneBase(BaseModel):
    """Base milestone schema."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[date] = None
    sequence: int = Field(0, ge=0)


class MilestoneCreate(MilestoneBase):
    """Milestone creation schema."""


class MilestoneUpdate(BaseModel):
    """Milestone update schema."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: Optional[MilestoneStatus] = None
    sequence: Optional[int] = Field(None, ge=0)


class MilestoneResponse(MilestoneBase):
    """Milestone response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    completed_date: Optional[date] = None
    status: MilestoneStatus
    created_at: datetime
    updated_at: datetime


class IndicatorBase(BaseModel):
    """Base indicator schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    baseline_value: Optional[Decimal] = None
    baseline_date: Optional[date] = None
    target_value: Optional[Decimal] = None
    target_date: Optional[date] = None


class IndicatorCreate(IndicatorBase):
    """Indicator creation schema."""

    organisation_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None


class IndicatorUpdate(BaseModel):
    """Indicator update schema.

    current_value is absent: it is derived from approved evidence rather than
    set by hand, so that a reported figure always traces to a record.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    baseline_value: Optional[Decimal] = None
    baseline_date: Optional[date] = None
    target_value: Optional[Decimal] = None
    target_date: Optional[date] = None


class IndicatorResponse(IndicatorBase):
    """Indicator response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    current_value: Optional[Decimal] = None
    current_value_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class SourceBase(BaseModel):
    """Base source schema."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field(..., min_length=1, max_length=50)
    url: Optional[str] = None
    description: Optional[str] = None


class SourceCreate(SourceBase):
    """Source creation schema."""

    organisation_id: uuid.UUID


class SourceResponse(SourceBase):
    """Source response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    credibility_score: int
    verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EvidenceBase(BaseModel):
    """Base evidence schema."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    evidence_date: Optional[date] = None
    beneficiaries: Optional[int] = None
    outcome: Optional[str] = None
    confidence_level: Optional[int] = Field(50, ge=0, le=100)


class EvidenceCreate(EvidenceBase):
    """Evidence creation schema."""

    organisation_id: uuid.UUID
    source_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None
    geography_id: Optional[uuid.UUID] = None
    indicator_id: Optional[uuid.UUID] = None
    measured_value: Optional[Decimal] = None


class EvidenceUpdate(BaseModel):
    """Evidence update schema.

    Workflow state (status, verification_status, approval_status, verified_by,
    approved_by) is intentionally absent: those transitions are owned by the
    dedicated verify, approve and publish endpoints and must not be settable
    through a general update.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    evidence_date: Optional[date] = None
    beneficiaries: Optional[int] = None
    outcome: Optional[str] = None
    confidence_level: Optional[int] = Field(None, ge=0, le=100)
    project_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None
    geography_id: Optional[uuid.UUID] = None
    indicator_id: Optional[uuid.UUID] = None
    measured_value: Optional[Decimal] = None
    document_url: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    metadata_json: Optional[dict[str, Any]] = None


class EvidenceResponse(EvidenceBase):
    """Evidence response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Permanent citable identifier, assigned once at creation.
    reference: str
    organisation_id: uuid.UUID
    source_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None
    geography_id: Optional[uuid.UUID] = None
    indicator_id: Optional[uuid.UUID] = None
    measured_value: Optional[Decimal] = None
    status: EvidenceStatus
    verification_status: str
    approval_status: str
    version: int
    created_at: datetime
    updated_at: datetime


class StoryBase(BaseModel):
    """Base story schema."""

    title: str = Field(..., min_length=1, max_length=255)
    headline: Optional[str] = None
    body: str = Field(..., min_length=1)
    summary: Optional[str] = None
    language: str = "en"


class StoryCreate(StoryBase):
    """Story creation schema.

    Tenancy is derived server-side from the linked evidence rather than
    accepted from the client.
    """

    evidence_id: uuid.UUID


class StoryUpdate(BaseModel):
    """Story update schema.

    Publication state (status, featured, approved_by, published_date) is owned
    by the publish and feature endpoints.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    headline: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = None
    language: Optional[str] = Field(None, max_length=5)


class StoryResponse(StoryBase):
    """Story response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    evidence_id: uuid.UUID
    status: str
    featured: bool
    published_date: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime


class QuestionBase(BaseModel):
    """Base question schema."""

    category: Optional[str] = None
    question_text: str = Field(..., min_length=1)
    location_state: Optional[str] = None
    location_lga: Optional[str] = None
    language: str = "en"
    is_anonymous: bool = True


class QuestionCreate(QuestionBase):
    """Question creation schema."""

    organisation_id: Optional[uuid.UUID] = None
    submitter_email: Optional[str] = None


class QuestionUpdate(BaseModel):
    """Question update schema.

    Workflow state (status, response, approved_by, is_published) is owned by the
    respond, approve, publish and close endpoints.
    """

    category: Optional[str] = Field(None, max_length=100)
    location_state: Optional[str] = Field(None, max_length=50)
    location_lga: Optional[str] = Field(None, max_length=100)
    assigned_to: Optional[uuid.UUID] = None


class QuestionResponse(QuestionBase):
    """Question response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: QuestionStatus
    response: Optional[str] = None
    response_date: Optional[datetime] = None
    is_published: bool
    created_at: datetime
    updated_at: datetime


class IntegritySignalBase(BaseModel):
    """Base integrity signal schema."""

    claim: str = Field(..., min_length=1)
    source: Optional[str] = None


class IntegritySignalCreate(IntegritySignalBase):
    """Integrity signal creation schema."""

    organisation_id: Optional[uuid.UUID] = None


class IntegritySignalResponse(IntegritySignalBase):
    """Integrity signal response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    priority: IntegritySignalPriority
    status: str
    verification_result: Optional[str] = None
    response: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScenarioBase(BaseModel):
    """Base scenario schema."""

    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None


class ScenarioCreate(ScenarioBase):
    """Scenario creation schema."""

    organisation_id: Optional[uuid.UUID] = None


class ScenarioResponse(ScenarioBase):
    """Scenario response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ReadinessStatus
    playbook_url: Optional[str] = None
    last_drill_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    """Paginated response envelope."""

    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[Any]
