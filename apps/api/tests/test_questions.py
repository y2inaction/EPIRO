"""Citizen question workflow tests.

Covers spec section 15's path from a public submission through triage,
research, response, approval and publication, and spec section 20's limit on
what may be collected about the person who asked.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ApprovalRecord, AuditLog, Organisation, Question
from app.models import QuestionStatus as Q
from app.models import Role
from tests.conftest import auth_header, make_area, make_organisation, member


def make_question(db: Session, organisation=None, **overrides) -> Question:
    """Create a persisted question."""
    fields = {
        "question_text": f"What happened to the borehole? {uuid.uuid4().hex[:8]}",
        "organisation_id": organisation.id if organisation is not None else None,
    }
    fields.update(overrides)

    question = Question(**fields)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def reload(db: Session, question: Question) -> Question:
    """Re-read a question after the API changed it."""
    db.expire_all()
    fresh = db.get(Question, question.id)
    assert fresh is not None
    return fresh


class TestPublicSubmission:
    def test_anyone_can_submit_a_question(self, client: TestClient, db: Session):
        response = client.post(
            "/api/v1/questions/",
            json={"question_text": "When will the clinic reopen?"},
        )

        assert response.status_code == 201
        assert response.json()["status"] == "new"

    def test_an_anonymous_question_cannot_carry_an_address(self, client: TestClient, db: Session):
        """Spec section 20: a record that says anonymous must not hold a contact."""
        response = client.post(
            "/api/v1/questions/",
            json={
                "question_text": "When will the clinic reopen?",
                "is_anonymous": True,
                "submitter_email": "someone@example.com",
            },
        )

        assert response.status_code == 422
        assert db.query(Question).count() == 0

    def test_an_identified_question_may_carry_an_address(self, client: TestClient, db: Session):
        response = client.post(
            "/api/v1/questions/",
            json={
                "question_text": "When will the clinic reopen?",
                "is_anonymous": False,
                "submitter_email": "someone@example.com",
            },
        )

        assert response.status_code == 201

    def test_the_response_never_carries_the_submitter_address(
        self, client: TestClient, db: Session
    ):
        response = client.post(
            "/api/v1/questions/",
            json={
                "question_text": "When will the clinic reopen?",
                "is_anonymous": False,
                "submitter_email": "someone@example.com",
            },
        )

        assert "submitter_email" not in response.json()

    def test_a_question_cannot_be_filed_against_an_unknown_organisation(
        self, client: TestClient, db: Session
    ):
        response = client.post(
            "/api/v1/questions/",
            json={
                "question_text": "When will the clinic reopen?",
                "organisation_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 400

    def test_the_submission_audit_entry_holds_nothing_about_the_submitter(
        self, client: TestClient, db: Session
    ):
        """The trail records how the body handled a question, not who asked."""
        client.post(
            "/api/v1/questions/",
            json={
                "question_text": "When will the clinic reopen?",
                "is_anonymous": False,
                "submitter_email": "someone@example.com",
            },
        )

        entry = db.query(AuditLog).filter(AuditLog.entity_type == "question").one()
        assert entry.user_id is None
        assert "someone@example.com" not in str(entry.new_values)
        assert "question_text" not in entry.new_values


class TestTriage:
    def test_an_untriaged_question_can_be_claimed(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Without triage every publicly submitted question was stuck forever."""
        question = make_question(db)
        area = make_area(db)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/triage",
            json={
                "organisation_id": str(organisation.id),
                "geography_id": str(area.id),
                "category": "health",
            },
            headers=auth_header(responder),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "triaged"

        fresh = reload(db, question)
        assert fresh.organisation_id == organisation.id
        assert fresh.geography_id == area.id

    def test_triage_requires_a_responder_role_in_the_receiving_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db)
        outsider = member(db, make_organisation(db), Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/triage",
            json={"organisation_id": str(organisation.id)},
            headers=auth_header(outsider),
        )

        assert response.status_code == 403

    def test_triage_rejects_an_unknown_area(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/triage",
            json={
                "organisation_id": str(organisation.id),
                "geography_id": str(uuid.uuid4()),
            },
            headers=auth_header(responder),
        )

        assert response.status_code == 400

    def test_an_already_triaged_question_cannot_be_retriaged(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db, organisation, status=Q.TRIAGED)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/triage",
            json={"organisation_id": str(organisation.id)},
            headers=auth_header(responder),
        )

        assert response.status_code == 409

    def test_the_public_inbox_is_listable_by_someone_who_could_triage(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Tenant scoping alone hid every unclaimed question from everyone."""
        make_question(db)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.get(
            "/api/v1/questions/", params={"untriaged": True}, headers=auth_header(responder)
        )

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_the_public_inbox_is_closed_to_someone_who_could_not(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_question(db)
        analyst = member(db, organisation, Role.ANALYST)

        response = client.get(
            "/api/v1/questions/", params={"untriaged": True}, headers=auth_header(analyst)
        )

        assert response.status_code == 403


class TestResponse:
    def test_a_response_is_drafted_through_the_body(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The answer used to travel in the query string, into every access log."""
        question = make_question(db, organisation, status=Q.TRIAGED)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/respond",
            json={"response": "The borehole was rehabilitated in June and is running."},
            headers=auth_header(responder),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "response_drafted"
        assert reload(db, question).response.startswith("The borehole")

    def test_an_untriaged_question_cannot_be_answered(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """It belongs to no organisation yet, so it is not the caller's to answer.

        Reported as missing rather than refused, the same way any record
        outside the caller's tenants is: the route in is triage.
        """
        question = make_question(db)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/respond",
            json={"response": "An answer."},
            headers=auth_header(responder),
        )

        assert response.status_code == 404
        assert reload(db, question).response is None

    def test_an_empty_response_is_refused(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db, organisation, status=Q.TRIAGED)
        responder = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/questions/{question.id}/respond",
            json={"response": ""},
            headers=auth_header(responder),
        )

        assert response.status_code == 422


class TestApproval:
    def test_the_responder_cannot_approve_their_own_answer(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        responder = member(db, organisation, Role.APPROVER)
        question = make_question(
            db,
            organisation,
            status=Q.RESPONSE_DRAFTED,
            response="An answer.",
            responded_by=responder.id,
        )

        response = client.post(
            f"/api/v1/questions/{question.id}/approve", headers=auth_header(responder)
        )

        assert response.status_code == 403

    def test_an_approval_is_recorded_in_the_trail(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db, organisation, status=Q.RESPONSE_DRAFTED, response="An answer.")
        approver = member(db, organisation, Role.APPROVER)

        client.post(
            f"/api/v1/questions/{question.id}/approve",
            json={"comments": "Accurate and in plain language."},
            headers=auth_header(approver),
        )

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == question.id).one()
        assert record.entity_type == "question"
        assert record.decision.value == "approved"
        assert record.comments == "Accurate and in plain language."

    def test_a_rejected_answer_goes_back_for_research(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(
            db, organisation, status=Q.RESPONSE_DRAFTED, response="A wrong answer."
        )
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/questions/{question.id}/reject",
            json={"comments": "This contradicts the project record."},
            headers=auth_header(approver),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "researching"

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == question.id).one()
        assert record.comments == "This contradicts the project record."

    def test_rejecting_an_approved_answer_clears_the_approval(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        approver = member(db, organisation, Role.APPROVER)
        question = make_question(
            db,
            organisation,
            status=Q.APPROVED,
            response="An answer.",
            approved_by=approver.id,
        )

        client.post(
            f"/api/v1/questions/{question.id}/reject",
            json={"comments": "Withdrawn on review."},
            headers=auth_header(approver),
        )

        assert reload(db, question).approved_by is None

    def test_a_rejection_without_a_reason_is_refused(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db, organisation, status=Q.RESPONSE_DRAFTED, response="An answer.")
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/questions/{question.id}/reject",
            json={"comments": ""},
            headers=auth_header(approver),
        )

        assert response.status_code == 422

    def test_the_trail_returns_every_round(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(
            db, organisation, status=Q.RESPONSE_DRAFTED, response="A first attempt."
        )
        approver = member(db, organisation, Role.APPROVER)
        responder = member(db, organisation, Role.RESEARCHER)

        client.post(
            f"/api/v1/questions/{question.id}/reject",
            json={"comments": "Not specific enough.", "changes_requested": True},
            headers=auth_header(approver),
        )
        client.post(
            f"/api/v1/questions/{question.id}/respond",
            json={"response": "A more specific answer."},
            headers=auth_header(responder),
        )
        client.post(f"/api/v1/questions/{question.id}/approve", headers=auth_header(approver))

        response = client.get(
            f"/api/v1/questions/{question.id}/approvals", headers=auth_header(approver)
        )

        assert [entry["decision"] for entry in response.json()] == [
            "changes_requested",
            "approved",
        ]


class TestPublication:
    def test_an_unapproved_answer_cannot_be_published(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db, organisation, status=Q.RESPONSE_DRAFTED, response="An answer.")
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/questions/{question.id}/publish", headers=auth_header(publisher)
        )

        assert response.status_code == 409

    def test_the_approver_cannot_also_publish(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        editor = member(db, organisation, Role.EDITOR)
        question = make_question(
            db, organisation, status=Q.APPROVED, response="An answer.", approved_by=editor.id
        )

        response = client.post(
            f"/api/v1/questions/{question.id}/publish", headers=auth_header(editor)
        )

        assert response.status_code == 403

    def test_an_approved_answer_publishes(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        approver = member(db, organisation, Role.APPROVER)
        question = make_question(
            db, organisation, status=Q.APPROVED, response="An answer.", approved_by=approver.id
        )
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/questions/{question.id}/publish", headers=auth_header(publisher)
        )

        assert response.status_code == 200
        assert response.json()["is_published"] is True


class TestAuditTrail:
    def test_the_whole_path_is_recorded(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db)
        responder = member(db, organisation, Role.RESEARCHER)
        approver = member(db, organisation, Role.APPROVER)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(
            f"/api/v1/questions/{question.id}/triage",
            json={"organisation_id": str(organisation.id)},
            headers=auth_header(responder),
        )
        client.post(
            f"/api/v1/questions/{question.id}/respond",
            json={"response": "An answer."},
            headers=auth_header(responder),
        )
        client.post(f"/api/v1/questions/{question.id}/approve", headers=auth_header(approver))
        client.post(f"/api/v1/questions/{question.id}/publish", headers=auth_header(publisher))
        client.post(f"/api/v1/questions/{question.id}/close", headers=auth_header(responder))

        actions = [
            entry.action
            for entry in db.query(AuditLog)
            .filter(AuditLog.entity_id == question.id)
            .order_by(AuditLog.created_at)
            .all()
        ]

        assert actions == ["triaged", "responded", "approved", "published", "closed"]


class TestTenancy:
    def test_another_tenants_question_is_not_visible(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        question = make_question(db, make_organisation(db))
        outsider = member(db, organisation, Role.RESEARCHER)

        response = client.get(f"/api/v1/questions/{question.id}", headers=auth_header(outsider))

        assert response.status_code == 404
