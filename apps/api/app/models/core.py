"""Core EPIRO models."""
# type: ignore

import uuid
from enum import Enum

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import relationship

from .base import TimestampedModel


class Role(str, Enum):
    """User roles."""

    SUPER_ADMIN = "super_admin"
    EXECUTIVE = "executive"
    EDITOR = "editor"
    EVIDENCE_MANAGER = "evidence_manager"
    RESEARCHER = "researcher"
    FIELD_OFFICER = "field_officer"
    VERIFIER = "verifier"
    INTEGRITY_ANALYST = "integrity_analyst"
    CONTENT_MANAGER = "content_manager"
    MEDIA_MANAGER = "media_manager"
    TRANSLATOR = "translator"
    APPROVER = "approver"
    ANALYST = "analyst"
    PUBLIC_USER = "public_user"


class EvidenceStatus(str, Enum):
    """Evidence lifecycle statuses."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class QuestionStatus(str, Enum):
    """Question workflow statuses."""

    NEW = "new"
    TRIAGED = "triaged"
    RESEARCHING = "researching"
    VERIFIED = "verified"
    RESPONSE_DRAFTED = "response_drafted"
    APPROVED = "approved"
    PUBLISHED = "published"
    CLOSED = "closed"


class IntegritySignalPriority(str, Enum):
    """Information integrity signal priority."""

    LOW_RISK = "low_risk"
    EMERGING = "emerging"
    MATERIAL = "material"
    CRISIS = "crisis"
    NATIONAL = "national"


class ReadinessStatus(str, Enum):
    """Readiness matrix status."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    BLACK = "black"


# Association tables
user_organisation = Table(
    "user_organisation",
    TimestampedModel.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column("organisation_id", UUID(as_uuid=True), ForeignKey("organisation.id"), primary_key=True),
    Column("role", SQLEnum(Role), default=Role.PUBLIC_USER),
)

programme_thematic = Table(
    "programme_thematic",
    TimestampedModel.metadata,
    Column("programme_id", UUID(as_uuid=True), ForeignKey("programme.id"), primary_key=True),
    Column("thematic_id", UUID(as_uuid=True), ForeignKey("thematic_area.id"), primary_key=True),
)


class Organisation(TimestampedModel):
    """Organisation model."""

    __tablename__ = "organisation"

    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    country = Column(String(2), default="NG")
    timezone = Column(String(50), default="Africa/Lagos")
    logo_url = Column(String(500))
    website = Column(String(500))
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSON, default={})

    # Relationships
    users = relationship("User", secondary=user_organisation, back_populates="organisations")
    programmes = relationship(
        "Programme", back_populates="organisation", cascade="all, delete-orphan"
    )
    projects = relationship("Project", back_populates="organisation", cascade="all, delete-orphan")
    evidence_items = relationship(
        "Evidence", back_populates="organisation", cascade="all, delete-orphan"
    )
    sources = relationship("Source", back_populates="organisation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_organisation_code", "code"),
        Index("idx_organisation_active", "is_active"),
    )


class User(TimestampedModel):
    """User model."""

    __tablename__ = "user"

    email = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(String)
    phone = Column(String(20))
    avatar_url = Column(String(500))
    timezone = Column(String(50))
    language = Column(String(5), default="en")
    preferences = Column(JSON, default={})

    # Relationships
    organisations = relationship(
        "Organisation", secondary=user_organisation, back_populates="users"
    )

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_active", "is_active"),
    )


class ThematicArea(TimestampedModel):
    """Thematic stream configuration."""

    __tablename__ = "thematic_area"

    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String(50))
    color = Column(String(7))
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Relationships
    programmes = relationship(
        "Programme",
        secondary=programme_thematic,
        back_populates="thematic_areas",
    )
    evidence_items = relationship("Evidence", back_populates="thematic_area")

    __table_args__ = (
        Index("idx_thematic_code", "code"),
        Index("idx_thematic_active", "is_active"),
    )


class Programme(TimestampedModel):
    """Programme model."""

    __tablename__ = "programme"

    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=False)
    description = Column(Text)
    organisation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organisation.id"),
        nullable=False,
    )
    start_date = Column(String)
    end_date = Column(String)
    budget = Column(Integer)
    status = Column(String(50), default="active")
    metadata_json = Column(JSON, default={})

    # Relationships
    organisation = relationship("Organisation", back_populates="programmes")
    projects = relationship("Project", back_populates="programme", cascade="all, delete-orphan")
    thematic_areas = relationship(
        "ThematicArea",
        secondary=programme_thematic,
        back_populates="programmes",
    )

    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_programme_org_code"),
        Index("idx_programme_org_id", "organisation_id"),
    )


class Project(TimestampedModel):
    """Project model."""

    __tablename__ = "project"

    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=False)
    description = Column(Text)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False)
    programme_id = Column(UUID(as_uuid=True), ForeignKey("programme.id"), nullable=True)
    start_date = Column(String)
    end_date = Column(String)
    budget = Column(Integer)
    status = Column(String(50), default="active")
    location_state = Column(String(50))
    location_lga = Column(String(100))
    location_community = Column(String(100))
    implementing_org = Column(String(255))
    target_beneficiaries = Column(Integer)
    metadata_json = Column(JSON, default={})

    # Relationships
    organisation = relationship("Organisation", back_populates="projects")
    programme = relationship("Programme", back_populates="projects")
    evidence_items = relationship("Evidence", back_populates="project")
    locations = relationship("Location", back_populates="project")

    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_project_org_code"),
        Index("idx_project_org_id", "organisation_id"),
        Index("idx_project_programme_id", "programme_id"),
    )


class Location(TimestampedModel):
    """Geographic location model."""

    __tablename__ = "location"

    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    state = Column(String(50))
    lga = Column(String(100))
    community = Column(String(100))
    latitude = Column(String)
    longitude = Column(String)
    geom = Column(Geometry("POINT", srid=4326), nullable=True)
    description = Column(Text)

    # Relationships
    project = relationship("Project", back_populates="locations")
    evidence_items = relationship("Evidence", back_populates="location")

    __table_args__ = (
        Index("idx_location_project_id", "project_id"),
        Index("idx_location_state", "state"),
    )


class Source(TimestampedModel):
    """Source registry model."""

    __tablename__ = "source"

    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # government, institutional, field, etc.
    url = Column(String(500))
    description = Column(Text)
    credibility_score = Column(Integer, default=50)  # 0-100
    verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSON, default={})

    # Relationships
    organisation = relationship("Organisation", back_populates="sources")
    evidence_items = relationship("Evidence", back_populates="source")

    __table_args__ = (
        Index("idx_source_organisation_id", "organisation_id"),
        Index("idx_source_type", "source_type"),
    )


class Evidence(TimestampedModel):
    """Evidence registry model."""

    __tablename__ = "evidence"

    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    location_id = Column(UUID(as_uuid=True), ForeignKey("location.id"), nullable=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("source.id"), nullable=False)
    thematic_area_id = Column(UUID(as_uuid=True), ForeignKey("thematic_area.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(EvidenceStatus), default=EvidenceStatus.DRAFT)
    evidence_date = Column(String)

    # Evidence details
    beneficiaries = Column(Integer)
    outcome = Column(Text)
    confidence_level = Column(Integer)  # 0-100

    # Files and media
    document_url = Column(String(500))
    image_urls = Column(ARRAY(String), default=[])
    video_urls = Column(ARRAY(String), default=[])

    # Verification
    verification_status = Column(String(50), default="unverified")
    verified_by = Column(UUID(as_uuid=True))
    verified_date = Column(String)
    verifier_notes = Column(Text)

    # Approval
    approval_status = Column(String(50), default="pending")
    approved_by = Column(UUID(as_uuid=True))
    approved_date = Column(String)

    # Metadata
    metadata_json = Column(JSON, default={})
    tags = Column(ARRAY(String), default=[])
    version = Column(Integer, default=1)

    # Relationships
    organisation = relationship("Organisation", back_populates="evidence_items")
    project = relationship("Project", back_populates="evidence_items")
    location = relationship("Location", back_populates="evidence_items")
    source = relationship("Source", back_populates="evidence_items")
    thematic_area = relationship("ThematicArea", back_populates="evidence_items")
    stories = relationship("Story", back_populates="evidence")
    audit_logs = relationship("AuditLog", back_populates="evidence")

    __table_args__ = (
        Index("idx_evidence_organisation_id", "organisation_id"),
        Index("idx_evidence_status", "status"),
        Index("idx_evidence_project_id", "project_id"),
    )


class Story(TimestampedModel):
    """Public information story model."""

    __tablename__ = "story"

    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=False)
    title = Column(String(255), nullable=False)
    headline = Column(String(500))
    body = Column(Text, nullable=False)
    summary = Column(Text)
    language = Column(String(5), default="en")
    status = Column(String(50), default="draft")
    featured = Column(Boolean, default=False)
    published_date = Column(String)
    version = Column(Integer, default=1)

    # Relationships
    evidence = relationship("Evidence", back_populates="stories")

    __table_args__ = (
        Index("idx_story_evidence_id", "evidence_id"),
        Index("idx_story_status", "status"),
    )


class Question(TimestampedModel):
    """Citizen question model."""

    __tablename__ = "question"

    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True)
    category = Column(String(100))
    question_text = Column(Text, nullable=False)
    location_state = Column(String(50))
    location_lga = Column(String(100))
    language = Column(String(5), default="en")
    is_anonymous = Column(Boolean, default=True)
    submitter_email = Column(String(255))
    status = Column(SQLEnum(QuestionStatus), default=QuestionStatus.NEW)
    assigned_to = Column(UUID(as_uuid=True))
    response = Column(Text)
    response_date = Column(String)
    approved_by = Column(UUID(as_uuid=True))
    is_published = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_question_status", "status"),
        Index("idx_question_organisation_id", "organisation_id"),
    )


class IntegritySignal(TimestampedModel):
    """Information integrity signal model."""

    __tablename__ = "integrity_signal"

    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True)
    claim = Column(Text, nullable=False)
    source = Column(String(255))
    priority = Column(SQLEnum(IntegritySignalPriority), default=IntegritySignalPriority.LOW_RISK)
    status = Column(String(50), default="new")
    assigned_to = Column(UUID(as_uuid=True))
    verification_result = Column(Text)
    response = Column(Text)
    approved_by = Column(UUID(as_uuid=True))

    __table_args__ = (
        Index("idx_integrity_priority", "priority"),
        Index("idx_integrity_status", "status"),
    )


class Scenario(TimestampedModel):
    """Readiness scenario model."""

    __tablename__ = "scenario"

    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True)
    name = Column(String(255), nullable=False)
    category = Column(String(50))  # policy, security, information, political, electoral, emergency
    description = Column(Text)
    trigger = Column(Text)
    status = Column(SQLEnum(ReadinessStatus), default=ReadinessStatus.GREEN)
    owner = Column(UUID(as_uuid=True))
    playbook_url = Column(String(500))
    last_drill_date = Column(String)

    __table_args__ = (Index("idx_scenario_status", "status"),)


class AuditLog(TimestampedModel):
    """Audit logging model."""

    __tablename__ = "audit_log"

    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=True)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Relationships
    evidence = relationship("Evidence", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_organisation_id", "organisation_id"),
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_action", "action"),
    )
