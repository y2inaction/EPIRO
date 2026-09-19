"""Approval trail tests.

Covers spec section 36: an approval decision keeps its reviewer, timestamp,
decision, comments and the version it was made against, and every round is
kept — including the ones that refused.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ApprovalRecord, AuditLog, Evidence, EvidenceStatus, Organisation, Role
from tests.conftest import auth_header, make_evidence, make_organisation, member


def verify(client: TestClient, db: Session, organisation: Organisation, evidence_id) -> None:
    """Take a record through verification by someone who can verify."""
    verifier = member(db, organisation, Role.VERIFIER)
    response = client.post(f"/api/v1/evidence/{evidence_id}/verify", headers=auth_header(verifier))
    assert response.status_code == 200


class TestRejection:
    def test_a_rejection_is_recorded_with_its_reason(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "The beneficiary count contradicts the attached register."},
            headers=auth_header(approver),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == evidence.id).one()
        assert record.decision.value == "rejected"
        assert record.reviewer_id == approver.id
        assert record.comments == "The beneficiary count contradicts the attached register."
        assert record.decided_at is not None

    def test_a_rejection_without_a_reason_is_refused(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A refusal with no stated reason gives the author nothing to act on."""
        evidence = make_evidence(db, organisation)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": ""},
            headers=auth_header(approver),
        )

        assert response.status_code == 422
        assert db.query(ApprovalRecord).count() == 0

    def test_changes_requested_is_distinguished_from_outright_rejection(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        approver = member(db, organisation, Role.APPROVER)

        client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "Add the register reference.", "changes_requested": True},
            headers=auth_header(approver),
        )

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == evidence.id).one()
        assert record.decision.value == "changes_requested"

    def test_rejecting_writes_an_audit_entry(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        approver = member(db, organisation, Role.APPROVER)

        client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "Source cannot be reached."},
            headers=auth_header(approver),
        )

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.entity_id == evidence.id, AuditLog.action == "rejected")
            .one()
        )
        assert entry.user_id == approver.id
        assert entry.new_values["comments"] == "Source cannot be reached."

    def test_published_evidence_cannot_be_rejected(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Retracting something already public is a withdrawal, not a refusal."""
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "Too late."},
            headers=auth_header(approver),
        )

        assert response.status_code == 409
        assert "Withdraw" in response.json()["detail"]
        assert db.query(ApprovalRecord).count() == 0

    def test_rejection_requires_the_approver_role(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        author = member(db, organisation, Role.FIELD_OFFICER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "I disagree with myself."},
            headers=auth_header(author),
        )

        assert response.status_code == 403

    def test_rejection_is_scoped_to_the_callers_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        evidence = make_evidence(db, other)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "Not mine to judge."},
            headers=auth_header(approver),
        )

        assert response.status_code == 404


class TestApprovalTrail:
    def test_every_round_is_kept_oldest_first(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The history is the point: a record that was refused once shows it."""
        evidence = make_evidence(db, organisation)
        approver = member(db, organisation, Role.APPROVER)

        client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "Missing the register.", "changes_requested": True},
            headers=auth_header(approver),
        )
        verify(client, db, organisation, evidence.id)
        client.post(
            f"/api/v1/evidence/{evidence.id}/approve",
            json={"comments": "Register now attached."},
            headers=auth_header(approver),
        )

        response = client.get(
            f"/api/v1/evidence/{evidence.id}/approvals", headers=auth_header(approver)
        )

        assert response.status_code == 200
        trail = response.json()
        assert [entry["decision"] for entry in trail] == ["changes_requested", "approved"]
        assert trail[0]["comments"] == "Missing the register."
        assert trail[1]["comments"] == "Register now attached."

    def test_an_approval_records_the_version_it_covered(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        author = member(db, organisation, Role.FIELD_OFFICER)
        approver = member(db, organisation, Role.APPROVER)

        client.put(
            f"/api/v1/evidence/{evidence.id}",
            json={"outcome": "Second draft."},
            headers=auth_header(author),
        )
        verify(client, db, organisation, evidence.id)
        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver))

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == evidence.id).one()
        assert record.entity_version == 2

    def test_an_approval_records_the_reviewer_and_when(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)

        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver))

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == evidence.id).one()
        assert record.reviewer_id == approver.id
        assert record.decision.value == "approved"
        assert record.decided_at is not None
        assert record.organisation_id == organisation.id

    def test_the_trail_is_not_readable_from_another_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        evidence = make_evidence(db, other)
        outsider = member(db, organisation, Role.APPROVER)

        response = client.get(
            f"/api/v1/evidence/{evidence.id}/approvals", headers=auth_header(outsider)
        )

        assert response.status_code == 404


class TestEditInvalidatesReview:
    def test_editing_raises_the_version(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        author = member(db, organisation, Role.FIELD_OFFICER)

        response = client.put(
            f"/api/v1/evidence/{evidence.id}",
            json={"outcome": "Revised."},
            headers=auth_header(author),
        )

        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_editing_an_approved_record_sends_it_back_for_review(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Otherwise an approval would cover content the approver never saw."""
        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)
        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver))

        author = member(db, organisation, Role.FIELD_OFFICER)
        client.put(
            f"/api/v1/evidence/{evidence.id}",
            json={"beneficiaries": 4000},
            headers=auth_header(author),
        )

        db.expire_all()
        reopened = db.get(Evidence, evidence.id)
        assert reopened is not None
        assert reopened.status is EvidenceStatus.DRAFT
        assert reopened.approval_status == "pending"
        assert reopened.approved_by is None
        assert reopened.verification_status == "unverified"
        assert reopened.verified_by is None

    def test_an_edited_record_cannot_be_published_on_its_old_approval(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)
        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver))

        author = member(db, organisation, Role.FIELD_OFFICER)
        client.put(
            f"/api/v1/evidence/{evidence.id}",
            json={"beneficiaries": 9000},
            headers=auth_header(author),
        )

        publisher = member(db, organisation, Role.CONTENT_MANAGER)
        response = client.post(
            f"/api/v1/evidence/{evidence.id}/publish", headers=auth_header(publisher)
        )

        assert response.status_code == 409

    def test_published_evidence_cannot_be_edited(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        author = member(db, organisation, Role.FIELD_OFFICER)

        response = client.put(
            f"/api/v1/evidence/{evidence.id}",
            json={"outcome": "Quietly different."},
            headers=auth_header(author),
        )

        assert response.status_code == 409
        db.expire_all()
        unchanged = db.get(Evidence, evidence.id)
        assert unchanged is not None
        assert unchanged.status is EvidenceStatus.PUBLISHED


class TestWithdrawal:
    def test_published_evidence_can_be_withdrawn_with_a_reason(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/withdraw",
            json={"reason": "The source has retracted its figures."},
            headers=auth_header(publisher),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "archived"

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.entity_id == evidence.id, AuditLog.action == "withdrawn")
            .one()
        )
        assert entry.new_values["reason"] == "The source has retracted its figures."
        assert entry.old_values["status"] == "published"

    def test_withdrawing_keeps_the_record(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Archiving, not deleting: the public record shows what was retracted."""
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(
            f"/api/v1/evidence/{evidence.id}/withdraw",
            json={"reason": "Figures restated."},
            headers=auth_header(publisher),
        )

        db.expire_all()
        assert db.get(Evidence, evidence.id) is not None

    def test_unpublished_evidence_cannot_be_withdrawn(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/withdraw",
            json={"reason": "Never mind."},
            headers=auth_header(publisher),
        )

        assert response.status_code == 409

    def test_withdrawal_requires_a_reason(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/withdraw",
            json={},
            headers=auth_header(publisher),
        )

        assert response.status_code == 422

    def test_withdrawal_requires_the_publisher_role(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        author = member(db, organisation, Role.FIELD_OFFICER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/withdraw",
            json={"reason": "Not my call."},
            headers=auth_header(author),
        )

        assert response.status_code == 403
