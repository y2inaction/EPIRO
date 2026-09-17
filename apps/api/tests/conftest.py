"""Pytest configuration and fixtures.

Tests run against a real PostgreSQL database with PostGIS, because the models
depend on JSONB, native enums, ARRAY and Geometry columns that SQLite cannot
represent. Each test runs inside a transaction that is rolled back afterwards,
so tests neither see nor leave behind each other's data.
"""

import os

# Must precede any app import: settings are read once at import time, and the
# login tests would otherwise exhaust the per-minute allowance. The dedicated
# rate-limit test re-enables the limiter for itself.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import uuid  # noqa: E402
from typing import Any, Dict, Generator, Optional  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Evidence,
    Geography,
    GeographyLevel,
    Organisation,
    Role,
    Source,
    Story,
    User,
    user_organisation,
)
from app.security import create_access_token, hash_password  # noqa: E402

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://epiro:epiro_password@localhost:5432/epiro_test",
)


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Create the test schema once for the whole session."""
    test_engine = create_engine(TEST_DATABASE_URL)

    with test_engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.commit()

    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """Provide a session whose work is rolled back after each test.

    The session joins the outer transaction as a savepoint, so endpoint code
    can call commit() normally while the outer rollback still discards
    everything.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """A TestClient bound to the transactional test session."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Factories -------------------------------------------------------------


def make_user(
    db: Session,
    email: Optional[str] = None,
    password: str = "correct-horse-battery",
    is_active: bool = True,
) -> User:
    """Create a persisted user."""
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:12]}@example.com",
        first_name="Test",
        last_name="User",
        password_hash=hash_password(password),
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_organisation(db: Session, code: Optional[str] = None) -> Organisation:
    """Create a persisted organisation."""
    suffix = uuid.uuid4().hex[:8]
    org = Organisation(
        name=f"Organisation {suffix}",
        code=code or f"org-{suffix}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def grant_role(db: Session, user: User, organisation: Organisation, role: Role) -> None:
    """Give a user a role within an organisation."""
    db.execute(
        user_organisation.insert().values(
            user_id=user.id,
            organisation_id=organisation.id,
            role=role,
        )
    )
    db.commit()


def make_source(db: Session, organisation: Organisation) -> Source:
    """Create a persisted source owned by an organisation."""
    source = Source(
        organisation_id=organisation.id,
        name=f"Source {uuid.uuid4().hex[:8]}",
        source_type="official_document",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def make_evidence(
    db: Session,
    organisation: Organisation,
    source: Optional[Source] = None,
    **overrides: Any,
) -> Evidence:
    """Create a persisted evidence record."""
    source = source or make_source(db, organisation)
    fields: Dict[str, Any] = {
        "organisation_id": organisation.id,
        "source_id": source.id,
        "title": f"Evidence {uuid.uuid4().hex[:8]}",
    }
    fields.update(overrides)

    evidence = Evidence(**fields)
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def make_story(db: Session, evidence: Evidence, **overrides: Any) -> Story:
    """Create a persisted story built from evidence."""
    fields: Dict[str, Any] = {
        "organisation_id": evidence.organisation_id,
        "evidence_id": evidence.id,
        "title": f"Story {uuid.uuid4().hex[:8]}",
        "body": "Body text.",
    }
    fields.update(overrides)

    story = Story(**fields)
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def make_area(
    db: Session,
    level: GeographyLevel = GeographyLevel.COUNTRY,
    parent: Optional[Geography] = None,
    name: Optional[str] = None,
) -> Geography:
    """Create a persisted geographic area."""
    area = Geography(
        level=level,
        name=name or f"Area {uuid.uuid4().hex[:8]}",
        parent_id=parent.id if parent is not None else None,
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


def make_area_chain(db: Session) -> Dict[str, Geography]:
    """Create a country / state / LGA chain, returned by level name."""
    country = make_area(db, GeographyLevel.COUNTRY)
    state = make_area(db, GeographyLevel.STATE, parent=country)
    lga = make_area(db, GeographyLevel.LGA, parent=state)
    return {"country": country, "state": state, "lga": lga}


def make_platform_admin(db: Session) -> User:
    """Create a platform-level administrator."""
    user = make_user(db)
    user.is_superuser = True
    db.commit()
    db.refresh(user)
    return user


def auth_header(user: User) -> Dict[str, str]:
    """Bearer header for a user."""
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def member(db: Session, organisation: Organisation, role: Role) -> User:
    """Create a user holding one role in an organisation."""
    user = make_user(db)
    grant_role(db, user, organisation, role)
    return user


# --- Common fixtures -------------------------------------------------------


@pytest.fixture
def organisation(db: Session) -> Organisation:
    """An organisation for the test to work in."""
    return make_organisation(db)


@pytest.fixture
def other_organisation(db: Session) -> Organisation:
    """A second, unrelated organisation, used to prove tenant isolation."""
    return make_organisation(db)


@pytest.fixture
def outsider(db: Session, other_organisation: Organisation) -> User:
    """A user with full rights, but only in an unrelated organisation.

    Deliberately a SUPER_ADMIN: the strongest organisation role must still
    confer nothing outside its own organisation.
    """
    return member(db, other_organisation, Role.SUPER_ADMIN)
