"""Core entity schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
    pass


class OrganisationResponse(OrganisationBase):
    """Organisation response schema."""
    id: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ThematicAreaBase(BaseModel):
    """Base thematic area schema."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class ThematicAreaResponse(ThematicAreaBase):
    """Thematic area response schema."""
    id: str
    is_active: bool

    class Config:
        from_attributes = True


class ProgrammeBase(BaseModel):
    """Base programme schema."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[int] = None


class ProgrammeCreate(ProgrammeBase):
    """Programme creation schema."""
    organisation_id: str


class ProgrammeResponse(ProgrammeBase):
    """Programme response schema."""
    id: str
    organisation_id: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[int] = None
    location_state: Optional[str] = None
    location_lga: Optional[str] = None
    location_community: Optional[str] = None
    implementing_org: Optional[str] = None
    target_beneficiaries: Optional[int] = None


class ProjectCreate(ProjectBase):
    """Project creation schema."""
    organisation_id: str
    programme_id: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Project response schema."""
    id: str
    organisation_id: str
    programme_id: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SourceBase(BaseModel):
    """Base source schema."""
    name: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field(..., min_length=1, max_length=50)
    url: Optional[str] = None
    description: Optional[str] = None


class SourceCreate(SourceBase):
    """Source creation schema."""
    organisation_id: str


class SourceResponse(SourceBase):
    """Source response schema."""
    id: str
    organisation_id: str
    credibility_score: int
    verified: bool
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class EvidenceBase(BaseModel):
    """Base evidence schema."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    evidence_date: Optional[str] = None
    beneficiaries: Optional[int] = None
    outcome: Optional[str] = None
    confidence_level: Optional[int] = 50


class EvidenceCreate(EvidenceBase):
    """Evidence creation schema."""
    organisation_id: str
    source_id: str
    project_id: Optional[str] = None
    location_id: Optional[str] = None
    thematic_area_id: Optional[str] = None


class EvidenceResponse(EvidenceBase):
    """Evidence response schema."""
    id: str
    organisation_id: str
    source_id: str
    project_id: Optional[str] = None
    location_id: Optional[str] = None
    thematic_area_id: Optional[str] = None
    status: str
    verification_status: str
    approval_status: str
    version: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class StoryBase(BaseModel):
    """Base story schema."""
    title: str = Field(..., min_length=1, max_length=255)
    headline: Optional[str] = None
    body: str = Field(..., min_length=1)
    summary: Optional[str] = None
    language: str = "en"


class StoryCreate(StoryBase):
    """Story creation schema."""
    evidence_id: str


class StoryResponse(StoryBase):
    """Story response schema."""
    id: str
    evidence_id: str
    status: str
    featured: bool
    published_date: Optional[str] = None
    version: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


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
    submitter_email: Optional[str] = None


class QuestionResponse(QuestionBase):
    """Question response schema."""
    id: str
    status: str
    response: Optional[str] = None
    response_date: Optional[str] = None
    is_published: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class IntegritySignalBase(BaseModel):
    """Base integrity signal schema."""
    claim: str = Field(..., min_length=1)
    source: Optional[str] = None


class IntegritySignalCreate(IntegritySignalBase):
    """Integrity signal creation schema."""
    organisation_id: Optional[str] = None


class IntegritySignalResponse(IntegritySignalBase):
    """Integrity signal response schema."""
    id: str
    priority: str
    status: str
    verification_result: Optional[str] = None
    response: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ScenarioBase(BaseModel):
    """Base scenario schema."""
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None


class ScenarioCreate(ScenarioBase):
    """Scenario creation schema."""
    organisation_id: Optional[str] = None


class ScenarioResponse(ScenarioBase):
    """Scenario response schema."""
    id: str
    status: str
    playbook_url: Optional[str] = None
    last_drill_date: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Paginated response schema."""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[dict]
