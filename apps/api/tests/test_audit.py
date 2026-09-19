"""Audit trail tests.

The AuditLog model existed from the start but nothing wrote to it, so these
assert that accountable actions actually leave a record.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import audit
from app.models import AuditLog, Organisation, Role
from tests.conftest import auth_header, make_evidence, make_user, member

PASSWORD = "correct-horse-battery"


def entries(db: Session, action: str) -> list[AuditLog]:
    """Audit entries recorded for one action."""
    return db.query(AuditLog).filter(AuditLog.action == action).all()


def test_login_is_recorded(client: TestClient, db: Session):
    user = make_user(db, password=PASSWORD)

    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200

    recorded = entries(db, audit.LOGIN)
    assert len(recorded) == 1
    assert recorded[0].user_id == user.id


def test_login_updates_last_login(client: TestClient, db: Session):
    """The column existed but was never written."""
    user = make_user(db, password=PASSWORD)
    assert user.last_login is None

    client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})

    db.refresh(user)
    assert user.last_login is not None


def test_a_failed_login_is_not_recorded_as_a_login(client: TestClient, db: Session):
    user = make_user(db, password=PASSWORD)

    client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong"})

    assert entries(db, audit.LOGIN) == []


def test_evidence_creation_is_recorded(client: TestClient, db: Session, organisation: Organisation):
    from tests.conftest import make_source

    author = member(db, organisation, Role.RESEARCHER)
    source = make_source(db, organisation)

    response = client.post(
        "/api/v1/evidence/",
        json={
            "title": "Clinic completion",
            "organisation_id": str(organisation.id),
            "source_id": str(source.id),
        },
        headers=auth_header(author),
    )
    assert response.status_code == 201

    recorded = entries(db, audit.CREATED)
    assert len(recorded) == 1
    assert recorded[0].user_id == author.id
    assert recorded[0].organisation_id == organisation.id
    assert recorded[0].new_values["title"] == "Clinic completion"


def test_verification_and_approval_record_who_acted(
    client: TestClient, db: Session, organisation: Organisation
):
    evidence = make_evidence(db, organisation)
    verifier = member(db, organisation, Role.VERIFIER)
    approver = member(db, organisation, Role.APPROVER)

    client.post(f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(verifier))
    client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver))

    verified = entries(db, audit.VERIFIED)
    approved = entries(db, audit.APPROVED)

    assert len(verified) == 1
    assert verified[0].user_id == verifier.id
    assert len(approved) == 1
    assert approved[0].user_id == approver.id
    # The trail shows two different people, which is the point of the gate.
    assert verified[0].user_id != approved[0].user_id


def test_deletion_preserves_what_was_removed(
    client: TestClient, db: Session, organisation: Organisation
):
    """A hard delete leaves no other record of the record's contents."""
    evidence = make_evidence(db, organisation, title="About to be deleted")
    manager = member(db, organisation, Role.EVIDENCE_MANAGER)

    response = client.delete(f"/api/v1/evidence/{evidence.id}", headers=auth_header(manager))
    assert response.status_code == 200

    recorded = entries(db, audit.DELETED)
    assert len(recorded) == 1
    assert recorded[0].old_values["title"] == "About to be deleted"
    assert recorded[0].user_id == manager.id


def test_update_records_both_old_and_new_values(
    client: TestClient, db: Session, organisation: Organisation
):
    evidence = make_evidence(db, organisation, title="Original title")
    author = member(db, organisation, Role.RESEARCHER)

    client.put(
        f"/api/v1/evidence/{evidence.id}",
        json={"title": "Revised title"},
        headers=auth_header(author),
    )

    recorded = entries(db, audit.UPDATED)
    assert len(recorded) == 1
    assert recorded[0].old_values["title"] == "Original title"
    assert recorded[0].new_values["title"] == "Revised title"


def test_a_rejected_action_leaves_no_audit_entry(
    client: TestClient, db: Session, organisation: Organisation
):
    """Only actions that actually happened should appear in the trail."""
    evidence = make_evidence(db, organisation)
    researcher = member(db, organisation, Role.RESEARCHER)

    response = client.post(
        f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(researcher)
    )
    assert response.status_code == 403
    assert entries(db, audit.VERIFIED) == []
