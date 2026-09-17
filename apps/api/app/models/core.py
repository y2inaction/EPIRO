"""Core EPIRO models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, Date, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampedModel


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    """Persist the enum's value rather than its member name.

    SQLAlchemy stores ``Enum.name`` by default, which would write "SUPER_ADMIN"
    while every API payload and client uses "super_admin". Storing values keeps
    the database and the wire format identical.
    """
    return [str(member.value) for member in enum_cls]


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
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column(
        "organisation_id",
        UUID(as_uuid=True),
        ForeignKey("organisation.id"),
        primary_key=True,
    ),
    Column(
        "role",
        SQLEnum(Role, values_callable=_enum_values),
        nullable=False,
        default=Role.PUBLIC_USER,
    ),
)

programme_thematic = Table(
    "programme_thematic",
    Base.metadata,
    Column("programme_id", UUID(as_uuid=True), ForeignKey("programme.id"), primary_key=True),
    Column(
        "thematic_id",
        UUID(as_uuid=True),
        ForeignKey("thematic_area.id"),
        primary_key=True,
    ),
)


class Organisation(TimestampedModel):
    """Organisation model."""

    __tablename__ = "organisation"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    country: Mapped[str] = mapped_column(String(2), default="NG", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Lagos", nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        secondary=user_organisation, back_populates="organisations"
    )
    programmes: Mapped[list["Programme"]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list["Evidence"]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )
    sources: Mapped[list["Source"]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )
    stories: Mapped[list["Story"]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_organisation_code", "code"),
        Index("idx_organisation_active", "is_active"),
    )


class User(TimestampedModel):
    """User model."""

    __tablename__ = "user"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Platform-level administration, distinct from the SUPER_ADMIN role, which
    # confers full rights within one organisation only.
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    timezone: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organisations: Mapped[list["Organisation"]] = relationship(
        secondary=user_organisation, back_populates="users"
    )

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_active", "is_active"),
    )


class ThematicArea(TimestampedModel):
    """Thematic stream configuration."""

    __tablename__ = "thematic_area"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(50))
    color: Mapped[Optional[str]] = mapped_column(String(7))
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    programmes: Mapped[list["Programme"]] = relationship(
        secondary=programme_thematic, back_populates="thematic_areas"
    )
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="thematic_area")

    __table_args__ = (
        Index("idx_thematic_code", "code"),
        Index("idx_thematic_active", "is_active"),
    )


class Programme(TimestampedModel):
    """Programme model."""

    __tablename__ = "programme"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    budget_currency: Mapped[Optional[str]] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organisation: Mapped["Organisation"] = relationship(back_populates="programmes")
    projects: Mapped[list["Project"]] = relationship(
        back_populates="programme", cascade="all, delete-orphan"
    )
    thematic_areas: Mapped[list["ThematicArea"]] = relationship(
        secondary=programme_thematic, back_populates="programmes"
    )

    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_programme_org_code"),
        Index("idx_programme_org_id", "organisation_id"),
    )


class Project(TimestampedModel):
    """Project model."""

    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False
    )
    programme_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programme.id"), nullable=True
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    budget_currency: Mapped[Optional[str]] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    location_state: Mapped[Optional[str]] = mapped_column(String(50))
    location_lga: Mapped[Optional[str]] = mapped_column(String(100))
    location_community: Mapped[Optional[str]] = mapped_column(String(100))
    implementing_org: Mapped[Optional[str]] = mapped_column(String(255))
    target_beneficiaries: Mapped[Optional[int]] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organisation: Mapped["Organisation"] = relationship(back_populates="projects")
    programme: Mapped[Optional["Programme"]] = relationship(back_populates="projects")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="project")
    locations: Mapped[list["Location"]] = relationship(back_populates="project")

    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_project_org_code"),
        Index("idx_project_org_id", "organisation_id"),
        Index("idx_project_programme_id", "programme_id"),
    )


class Location(TimestampedModel):
    """Geographic location model."""

    __tablename__ = "location"

    # Nullable so a location can be recorded for evidence that is not tied to a
    # project.
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=True
    )
    state: Mapped[Optional[str]] = mapped_column(String(50))
    lga: Mapped[Optional[str]] = mapped_column(String(100))
    community: Mapped[Optional[str]] = mapped_column(String(100))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    geom: Mapped[Optional[Any]] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="locations")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="location")

    __table_args__ = (
        Index("idx_location_project_id", "project_id"),
        Index("idx_location_state", "state"),
    )


class Source(TimestampedModel):
    """Source registry model."""

    __tablename__ = "source"

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    credibility_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organisation: Mapped["Organisation"] = relationship(back_populates="sources")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="source")

    __table_args__ = (
        Index("idx_source_organisation_id", "organisation_id"),
        Index("idx_source_type", "source_type"),
    )


class Evidence(TimestampedModel):
    """Evidence registry model."""

    __tablename__ = "evidence"

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=True
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("location.id"), nullable=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source.id"), nullable=False
    )
    thematic_area_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("thematic_area.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[EvidenceStatus] = mapped_column(
        SQLEnum(EvidenceStatus, values_callable=_enum_values),
        default=EvidenceStatus.DRAFT,
        nullable=False,
    )
    evidence_date: Mapped[Optional[date]] = mapped_column(Date)

    # Evidence details
    beneficiaries: Mapped[Optional[int]] = mapped_column(Integer)
    outcome: Mapped[Optional[str]] = mapped_column(Text)
    confidence_level: Mapped[Optional[int]] = mapped_column(Integer)

    # Files and media
    document_url: Mapped[Optional[str]] = mapped_column(String(500))
    image_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    video_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Verification
    verification_status: Mapped[str] = mapped_column(
        String(50), default="unverified", nullable=False
    )
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    verified_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    verifier_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Approval
    approval_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Metadata
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    organisation: Mapped["Organisation"] = relationship(back_populates="evidence_items")
    project: Mapped[Optional["Project"]] = relationship(back_populates="evidence_items")
    location: Mapped[Optional["Location"]] = relationship(back_populates="evidence_items")
    source: Mapped["Source"] = relationship(back_populates="evidence_items")
    thematic_area: Mapped[Optional["ThematicArea"]] = relationship(back_populates="evidence_items")
    stories: Mapped[list["Story"]] = relationship(back_populates="evidence")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="evidence")

    __table_args__ = (
        Index("idx_evidence_organisation_id", "organisation_id"),
        Index("idx_evidence_status", "status"),
        Index("idx_evidence_project_id", "project_id"),
    )


class Story(TimestampedModel):
    """Public information story model."""

    __tablename__ = "story"

    # Tenancy is carried explicitly rather than inferred through evidence, so
    # story queries can be scoped without a join.
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=False
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[Optional[str]] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    organisation: Mapped["Organisation"] = relationship(back_populates="stories")
    evidence: Mapped["Evidence"] = relationship(back_populates="stories")

    __table_args__ = (
        Index("idx_story_evidence_id", "evidence_id"),
        Index("idx_story_organisation_id", "organisation_id"),
        Index("idx_story_status", "status"),
    )


class Question(TimestampedModel):
    """Citizen question model."""

    __tablename__ = "question"

    organisation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100))
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    location_state: Mapped[Optional[str]] = mapped_column(String(50))
    location_lga: Mapped[Optional[str]] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    submitter_email: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[QuestionStatus] = mapped_column(
        SQLEnum(QuestionStatus, values_callable=_enum_values),
        default=QuestionStatus.NEW,
        nullable=False,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    response: Mapped[Optional[str]] = mapped_column(Text)
    # Recorded separately from updated_by so approval can require a different
    # person from whoever drafted the response.
    responded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    response_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_question_status", "status"),
        Index("idx_question_organisation_id", "organisation_id"),
    )


class IntegritySignal(TimestampedModel):
    """Information integrity signal model."""

    __tablename__ = "integrity_signal"

    organisation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255))
    priority: Mapped[IntegritySignalPriority] = mapped_column(
        SQLEnum(IntegritySignalPriority, values_callable=_enum_values),
        default=IntegritySignalPriority.LOW_RISK,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    verification_result: Mapped[Optional[str]] = mapped_column(Text)
    response: Mapped[Optional[str]] = mapped_column(Text)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    __table_args__ = (
        Index("idx_integrity_priority", "priority"),
        Index("idx_integrity_status", "status"),
    )


class Scenario(TimestampedModel):
    """Readiness scenario model."""

    __tablename__ = "scenario"

    organisation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    trigger: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ReadinessStatus] = mapped_column(
        SQLEnum(ReadinessStatus, values_callable=_enum_values),
        default=ReadinessStatus.GREEN,
        nullable=False,
    )
    owner: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    playbook_url: Mapped[Optional[str]] = mapped_column(String(500))
    last_drill_date: Mapped[Optional[date]] = mapped_column(Date)

    __table_args__ = (Index("idx_scenario_status", "status"),)


class AuditLog(TimestampedModel):
    """Audit logging model."""

    __tablename__ = "audit_log"

    organisation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisation.id"), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    old_values: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    evidence: Mapped[Optional["Evidence"]] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_organisation_id", "organisation_id"),
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_action", "action"),
    )
