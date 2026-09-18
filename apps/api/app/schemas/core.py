"""Core entity schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.core import (
    ApprovalDecision,
    EvidenceStatus,
    GeographyLevel,
    IntegrityFinding,
    IntegritySignalPriority,
    IntegritySignalStatus,
    MilestoneStatus,
    ProjectStatus,
    QuestionStatus,
    ReadinessStatus,
    SourceReliability,
    SourceType,
    StoryStatus,
    VerificationState,
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
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    order: int = Field(0, ge=0)


class ThematicAreaCreate(ThematicAreaBase):
    """Thematic area creation schema.

    The eight streams in spec section 9 are seeded, not hard-coded, so an
    administrator can add more.
    """


class ThematicAreaUpdate(BaseModel):
    """Thematic area update schema.

    Code is absent: it is the stable identifier existing records were filed
    under, so changing it would silently reinterpret them.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ThematicAreaResponse(ThematicAreaBase):
    """Thematic area response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


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


class ProgrammeUpdate(BaseModel):
    """Programme update schema.

    Code is absent: it is the identifier projects are filed under within an
    organisation.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    budget_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    status: Optional[str] = Field(None, max_length=50)


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
    source_type: SourceType
    url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    publisher: Optional[str] = Field(None, max_length=255)
    author: Optional[str] = Field(None, max_length=255)
    publication_date: Optional[date] = None
    document_url: Optional[str] = Field(None, max_length=500)
    document_hash: Optional[str] = Field(None, max_length=128)
    provenance: Optional[str] = None


class SourceCreate(SourceBase):
    """Source creation schema."""

    organisation_id: uuid.UUID


class SourceUpdate(BaseModel):
    """Source update schema.

    Verification state and reliability are absent: both are review outcomes
    and move through the dedicated review endpoint, which records who decided
    and why.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    source_type: Optional[SourceType] = None
    url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    publisher: Optional[str] = Field(None, max_length=255)
    author: Optional[str] = Field(None, max_length=255)
    publication_date: Optional[date] = None
    document_url: Optional[str] = Field(None, max_length=500)
    document_hash: Optional[str] = Field(None, max_length=128)
    provenance: Optional[str] = None
    is_active: Optional[bool] = None


class SourceReview(BaseModel):
    """Record the outcome of reviewing a source."""

    verification_state: VerificationState
    reliability: SourceReliability = SourceReliability.UNKNOWN
    # Required so a classification is never an unexplained judgement.
    rationale: str = Field(..., min_length=1)
    next_review_date: Optional[date] = None


class SourceResponse(SourceBase):
    """Source response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    verification_state: VerificationState
    reliability: SourceReliability
    reliability_rationale: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    review_date: Optional[date] = None
    next_review_date: Optional[date] = None
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
    status: StoryStatus
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
    """Question creation schema.

    A submitter address is only accepted alongside is_anonymous=false. Storing
    a contact detail on a record that describes itself as anonymous would be a
    false statement to the person who submitted it, and spec section 20 limits
    collection to what an operational purpose requires.
    """

    organisation_id: Optional[uuid.UUID] = None
    submitter_email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def _anonymous_submissions_carry_no_address(self) -> "QuestionCreate":
        if self.is_anonymous and self.submitter_email is not None:
            raise ValueError(
                "An anonymous question cannot carry a submitter address. "
                "Set is_anonymous to false to be contacted about it."
            )
        return self


class QuestionTriage(BaseModel):
    """Assigning a publicly submitted question to the body that will answer it.

    Until this happens a question belongs to no organisation, so there is no
    tenant against which to check a role and nothing can act on it.
    """

    organisation_id: uuid.UUID
    geography_id: Optional[uuid.UUID] = None
    category: Optional[str] = Field(None, max_length=100)
    assigned_to: Optional[uuid.UUID] = None


class QuestionResponseDraft(BaseModel):
    """A drafted answer.

    Carried in the body rather than the query string: an answer in a URL is
    written to every access log and proxy along the way, and truncated by the
    first one with a length limit.
    """

    response: str = Field(..., min_length=1, max_length=20000)


class QuestionUpdate(BaseModel):
    """Question update schema.

    Workflow state (status, response, approved_by, is_published) is owned by the
    respond, approve, publish and close endpoints.
    """

    category: Optional[str] = Field(None, max_length=100)
    location_state: Optional[str] = Field(None, max_length=50)
    location_lga: Optional[str] = Field(None, max_length=100)
    geography_id: Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None


class QuestionResponse(QuestionBase):
    """Question response schema.

    Carries organisation_id because roles are held per organisation: a client
    cannot tell which actions to offer on a question without knowing which body
    it was triaged to. It is not a disclosure — a caller only ever sees
    questions in organisations they already belong to, or ones nobody has
    claimed at all.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: Optional[uuid.UUID] = None
    status: QuestionStatus
    response: Optional[str] = None
    response_date: Optional[datetime] = None
    is_published: bool
    created_at: datetime
    updated_at: datetime


class IntegritySignalBase(BaseModel):
    """A claim circulating in public, described as information.

    Every field here is about the claim or the channel carrying it. There is
    deliberately no field naming a person who spread it: spec section 4 forbids
    profiling citizens, and a schema that accepted such a field would be the
    first place the prohibition leaked.
    """

    claim: str = Field(..., min_length=1, max_length=5000)
    source: Optional[str] = Field(
        None,
        max_length=255,
        description="The channel it was observed on, not the person who posted it",
    )
    circulation: Optional[str] = Field(
        None,
        max_length=5000,
        description="How and where it is spreading, described as channels",
    )
    first_observed: Optional[date] = None
    language: str = Field("en", max_length=5)
    geography_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None


class IntegritySignalCreate(IntegritySignalBase):
    """Log a claim that needs looking at."""

    organisation_id: uuid.UUID
    priority: IntegritySignalPriority = IntegritySignalPriority.LOW_RISK
    assigned_to: Optional[uuid.UUID] = None


class IntegritySignalUpdate(BaseModel):
    """Revise the description of a signal.

    Editing what the claim says invalidates any assessment of it, because the
    assessment answered the old wording. The API raises the version and sends
    the record back accordingly.
    """

    claim: Optional[str] = Field(None, min_length=1, max_length=5000)
    source: Optional[str] = Field(None, max_length=255)
    circulation: Optional[str] = Field(None, max_length=5000)
    first_observed: Optional[date] = None
    language: Optional[str] = Field(None, max_length=5)
    geography_id: Optional[uuid.UUID] = None
    thematic_area_id: Optional[uuid.UUID] = None
    priority: Optional[IntegritySignalPriority] = None
    assigned_to: Optional[uuid.UUID] = None


class IntegrityAssessment(BaseModel):
    """What was found out about a claim, and why.

    Both fields are required together. A finding with no reasoning is an
    unexplainable verdict, which spec section 4 rules out; reasoning with no
    finding leaves the record unable to say what it concluded.
    """

    finding: IntegrityFinding
    assessment: str = Field(..., min_length=1, max_length=20000)
    impact: Optional[str] = Field(None, max_length=20000)
    evidence_id: Optional[uuid.UUID] = Field(
        None,
        description="The evidence record the finding rests on",
    )


class IntegrityResponseDraft(BaseModel):
    """The correction the body intends to put out."""

    response: str = Field(..., min_length=1, max_length=20000)


class IntegritySignalResponse(IntegritySignalBase):
    """An integrity signal as the workspace sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    priority: IntegritySignalPriority
    status: IntegritySignalStatus
    assigned_to: Optional[uuid.UUID] = None
    finding: Optional[IntegrityFinding] = None
    assessment: Optional[str] = None
    impact: Optional[str] = None
    evidence_id: Optional[uuid.UUID] = None
    assessed_by: Optional[uuid.UUID] = None
    assessed_at: Optional[datetime] = None
    response: Optional[str] = None
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    version: int
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


class VerificationNotes(BaseModel):
    """What a verifier found when checking a record against its source.

    Carried in the body rather than the query string. These notes are internal
    and can name people who were contacted to confirm a figure; a query string
    is written into every access log and proxy along the way.
    """

    notes: str = Field("", max_length=5000)


class ApprovalDecisionRequest(BaseModel):
    """Optional detail supplied with an approval decision."""

    comments: Optional[str] = Field(None, max_length=2000)


class RejectionRequest(BaseModel):
    """Detail supplied when refusing a record.

    Comments are required: a rejection without a stated reason gives the author
    nothing to act on.
    """

    comments: str = Field(..., min_length=1, max_length=2000)
    changes_requested: bool = Field(
        False,
        description="True when the record should be revised rather than abandoned",
    )


class WithdrawalRequest(BaseModel):
    """Detail supplied when retracting something already published.

    A reason is required: the point of withdrawing rather than deleting is that
    the record states why what was published no longer stands.
    """

    reason: str = Field(..., min_length=1, max_length=2000)


class ApprovalRecordResponse(BaseModel):
    """One decision in the approval trail."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    entity_version: Optional[int] = None
    decision: ApprovalDecision
    reviewer_id: uuid.UUID
    decided_at: datetime
    comments: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response envelope."""

    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[Any]


class WorkflowStageInput(BaseModel):
    """One review stage in a workflow definition."""

    name: str = Field(..., min_length=1, max_length=160)
    required_roles: List[str] = Field(..., min_length=1)
    requires_distinct_actor: bool = Field(
        True,
        description=(
            "Whether whoever clears this stage must differ from whoever cleared "
            "the previous one. Forced true on the final stage."
        ),
    )


class WorkflowDefinitionCreate(BaseModel):
    """A workflow an organisation defines for one kind of content.

    Stages are given in the order they must be cleared. The coarse lifecycle
    around them — draft, approved, published, withdrawn — is not configurable:
    see app/services/workflow.py for why.
    """

    organisation_id: uuid.UUID
    entity_type: str = Field(..., pattern="^(evidence|story|question)$")
    name: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = None
    stages: List[WorkflowStageInput] = Field(..., min_length=1)


class WorkflowStageResponse(BaseModel):
    """A stage as stored."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    name: str
    required_roles: List[str]
    requires_distinct_actor: bool


class WorkflowDefinitionResponse(BaseModel):
    """A workflow definition and its stages, in order."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    entity_type: str
    name: str
    description: Optional[str] = None
    is_active: bool
    stages: List[WorkflowStageResponse] = []


class WorkflowProgressResponse(BaseModel):
    """How far a record has got through its organisation's workflow."""

    definition_name: Optional[str] = None
    current_stage: Optional[str] = None
    cleared: int
    total: int
    is_final_stage: bool
