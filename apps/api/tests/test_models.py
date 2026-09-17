"""Model behaviour tests.

These assert the data-modelling corrections made during the rebuild, so a
regression shows up as a failing test rather than as silently wrong data.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Organisation, Programme
from tests.conftest import make_evidence, make_organisation, make_story


def test_enum_columns_persist_their_value_not_member_name(db: Session, organisation: Organisation):
    """SQLAlchemy stores Enum.name by default, which the API never uses."""
    evidence = make_evidence(db, organisation)

    stored = db.execute(
        text("SELECT status FROM evidence WHERE id = :id"), {"id": evidence.id}
    ).scalar_one()

    assert stored == "draft"


def test_json_defaults_are_not_shared_between_instances(db: Session):
    """A mutable default={} would be one dict shared by every row."""
    first = make_organisation(db)
    second = make_organisation(db)

    assert first.metadata_json is not second.metadata_json


def test_story_carries_its_own_organisation(db: Session, organisation: Organisation):
    """Without this column, story queries cannot be tenant-scoped at all."""
    evidence = make_evidence(db, organisation)
    story = make_story(db, evidence)

    assert story.organisation_id == organisation.id


def test_timestamps_are_timezone_aware(db: Session, organisation: Organisation):
    evidence = make_evidence(db, organisation)

    assert isinstance(evidence.created_at, datetime)
    assert evidence.created_at.tzinfo is not None


def test_dates_round_trip_as_dates_not_strings(db: Session, organisation: Organisation):
    evidence = make_evidence(db, organisation, evidence_date=date(2026, 3, 1))

    db.refresh(evidence)
    assert evidence.evidence_date == date(2026, 3, 1)


def test_budget_keeps_decimal_precision(db: Session, organisation: Organisation):
    """Money stored as Integer silently lost minor units."""
    programme = Programme(
        organisation_id=organisation.id,
        name="Rural water",
        code="rw-1",
        budget=Decimal("12345678.90"),
        budget_currency="NGN",
    )
    db.add(programme)
    db.commit()
    db.refresh(programme)

    assert programme.budget == Decimal("12345678.90")
