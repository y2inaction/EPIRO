"""Rate limiting tests.

The limiter is disabled for the rest of the suite (see conftest), so these
turn it back on for themselves and put it back afterwards.
"""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.rate_limit import limiter
from tests.conftest import make_user

PASSWORD = "correct-horse-battery"


@pytest.fixture
def enabled_limiter() -> Generator[None, None, None]:
    """Enable the limiter with empty counters for one test."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_repeated_failed_logins_are_throttled(
    client: TestClient, db: Session, enabled_limiter: None
):
    """Without this, the login endpoint is an unbounded password oracle."""
    user = make_user(db, password=PASSWORD)
    allowance = settings.rate_limit_login_per_minute

    statuses = [
        client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrong-password"},
        ).status_code
        for _ in range(allowance + 1)
    ]

    assert statuses[:allowance] == [401] * allowance
    assert statuses[-1] == 429


def test_public_question_submission_is_throttled(
    client: TestClient, db: Session, enabled_limiter: None
):
    """The endpoint takes no credentials, so it is otherwise a spam channel."""
    allowance = settings.rate_limit_public_write_per_minute

    statuses = [
        client.post(
            "/api/v1/questions/",
            json={"question_text": f"What changed near me? {index}"},
        ).status_code
        for index in range(allowance + 1)
    ]

    assert statuses[-1] == 429
    assert all(code == 201 for code in statuses[:allowance])


def test_the_limiter_is_off_for_the_rest_of_the_suite(client: TestClient, db: Session):
    """Guards the fixture: a leaked enabled limiter would break other tests."""
    assert limiter.enabled is False
