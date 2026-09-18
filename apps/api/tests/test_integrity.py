"""Information integrity workflow (spec sections 25-26).

The rules worth holding onto, and the tests that hold them:

* A determination about a claim cannot be approved unless it cites evidence the
  organisation has itself approved — spec section 4's "explainable,
  source-linked". ``UNRESOLVED`` is the one finding exempt, because it asserts
  nothing to source.
* The person who wrote the assessment may not approve it, and the person who
  approved it may not publish it.
* Rewording a claim throws away the finding, because the finding answered
  different words.
* The published record identifies nobody — not the reviewers, and above all not
  whoever was repeating the claim.
"""

import uuid
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Evidence,
    EvidenceStatus,
    IntegrityFinding,
    IntegritySignal,
    IntegritySignalPriority,
    IntegritySignalStatus,
    Organisation,
    Role,
    User,
)
from app.schemas.public import PublicCorrection
from tests.conftest import auth_header, make_evidence, member

BASE = "/api/v1/integrity"

CLAIM = "The borehole programme in Bida was cancelled and the money returned."


@pytest.fixture
def monitor(db: Session, organisation: Organisation) -> User:
    """Someone who logs what is circulating."""
    return member(db, organisation, Role.FIELD_OFFICER)


@pytest.fixture
def assessor(db: Session, organisation: Organisation) -> User:
    """Someone who may decide what is true about a claim."""
    return member(db, organisation, Role.INTEGRITY_ANALYST)


@pytest.fixture
def approver(db: Session, organisation: Organisation) -> User:
    return member(db, organisation, Role.APPROVER)


@pytest.fixture
def publisher(db: Session, organisation: Organisation) -> User:
    return member(db, organisation, Role.CONTENT_MANAGER)


def approved_evidence(db: Session, organisation: Organisation) -> Evidence:
    """An evidence record that has cleared approval."""
    return make_evidence(db, organisation, status=EvidenceStatus.APPROVED)


def log_signal(
    client: TestClient,
    user: User,
    organisation: Organisation,
    **overrides: Any,
) -> Dict[str, Any]:
    """Log a signal and return the created record."""
    payload: Dict[str, Any] = {
        "organisation_id": str(organisation.id),
        "claim": CLAIM,
        "source": "Voice notes forwarded on WhatsApp",
    }
    payload.update(overrides)

    response = client.post(f"{BASE}/", json=payload, headers=auth_header(user))
    assert response.status_code == 201, response.text
    return response.json()


def assess(
    client: TestClient,
    user: User,
    signal_id: str,
    finding: IntegrityFinding = IntegrityFinding.FALSE,
    evidence_id: Optional[uuid.UUID] = None,
) -> Any:
    """Record a finding against a signal."""
    body: Dict[str, Any] = {
        "finding": finding.value,
        "assessment": "The programme's own milestone records show it is running.",
    }
    if evidence_id is not None:
        body["evidence_id"] = str(evidence_id)

    return client.post(f"{BASE}/{signal_id}/assess", json=body, headers=auth_header(user))


def take_to_approved(
    client: TestClient,
    db: Session,
    organisation: Organisation,
    assessor: User,
    approver: User,
    monitor: User,
) -> Dict[str, Any]:
    """Drive a signal as far as an approved finding with a drafted response."""
    signal = log_signal(client, monitor, organisation)
    evidence = approved_evidence(db, organisation)

    assert assess(client, assessor, signal["id"], evidence_id=evidence.id).status_code == 200

    response = client.post(
        f"{BASE}/{signal['id']}/respond",
        json={"response": "The programme is running; 14 boreholes were completed in August."},
        headers=auth_header(assessor),
    )
    assert response.status_code == 200, response.text

    approved = client.post(f"{BASE}/{signal['id']}/approve", json={}, headers=auth_header(approver))
    assert approved.status_code == 200, approved.text
    return approved.json()


# --- Logging ---------------------------------------------------------------


class TestLogging:
    def test_a_monitor_can_log_a_circulating_claim(
        self, client: TestClient, monitor: User, organisation: Organisation
    ):
        signal = log_signal(client, monitor, organisation)

        assert signal["claim"] == CLAIM
        assert signal["status"] == IntegritySignalStatus.NEW.value
        assert signal["priority"] == IntegritySignalPriority.LOW_RISK.value
        assert signal["finding"] is None

    def test_someone_without_a_monitoring_role_cannot_log_one(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        translator = member(db, organisation, Role.TRANSLATOR)

        response = client.post(
            f"{BASE}/",
            json={"organisation_id": str(organisation.id), "claim": CLAIM},
            headers=auth_header(translator),
        )

        assert response.status_code == 403

    def test_an_outsider_cannot_log_against_another_body(
        self, client: TestClient, outsider: User, organisation: Organisation
    ):
        response = client.post(
            f"{BASE}/",
            json={"organisation_id": str(organisation.id), "claim": CLAIM},
            headers=auth_header(outsider),
        )

        assert response.status_code == 403

    def test_logging_is_recorded_in_the_audit_trail(
        self, client: TestClient, db: Session, monitor: User, organisation: Organisation
    ):
        signal = log_signal(client, monitor, organisation)

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "integrity_signal",
                AuditLog.entity_id == uuid.UUID(signal["id"]),
            )
            .one()
        )
        assert entry.action == "created"
        assert entry.user_id == monitor.id


# --- Assessment ------------------------------------------------------------


class TestAssessment:
    def test_an_assessor_records_a_finding_and_its_reasoning(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        organisation: Organisation,
    ):
        signal = log_signal(client, monitor, organisation)
        evidence = approved_evidence(db, organisation)

        response = assess(client, assessor, signal["id"], evidence_id=evidence.id)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["finding"] == IntegrityFinding.FALSE.value
        assert body["assessment"]
        assert body["status"] == IntegritySignalStatus.ASSESSED.value
        assert body["assessed_by"] == str(assessor.id)

    def test_a_verdict_without_reasoning_is_not_expressible(
        self, client: TestClient, monitor: User, assessor: User, organisation: Organisation
    ):
        """Spec section 4: intelligence must be explainable."""
        signal = log_signal(client, monitor, organisation)

        response = client.post(
            f"{BASE}/{signal['id']}/assess",
            json={"finding": IntegrityFinding.FALSE.value},
            headers=auth_header(assessor),
        )

        assert response.status_code == 422

    def test_a_monitor_cannot_decide_what_is_true(
        self, client: TestClient, monitor: User, organisation: Organisation
    ):
        signal = log_signal(client, monitor, organisation)

        response = assess(client, monitor, signal["id"])

        assert response.status_code == 403

    def test_evidence_from_another_body_cannot_be_cited(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        organisation: Organisation,
        other_organisation: Organisation,
    ):
        signal = log_signal(client, monitor, organisation)
        theirs = approved_evidence(db, other_organisation)

        response = assess(client, assessor, signal["id"], evidence_id=theirs.id)

        assert response.status_code == 400


# --- Approval --------------------------------------------------------------


class TestApproval:
    def test_a_determination_must_cite_evidence(
        self,
        client: TestClient,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        """The rule that makes a correction checkable rather than asserted."""
        signal = log_signal(client, monitor, organisation)
        assert assess(client, assessor, signal["id"]).status_code == 200

        response = client.post(
            f"{BASE}/{signal['id']}/approve", json={}, headers=auth_header(approver)
        )

        assert response.status_code == 400
        assert "cite the evidence" in response.json()["detail"]

    def test_unresolved_needs_no_source_because_it_asserts_nothing(
        self,
        client: TestClient,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = log_signal(client, monitor, organisation)
        assert (
            assess(client, assessor, signal["id"], finding=IntegrityFinding.UNRESOLVED).status_code
            == 200
        )

        response = client.post(
            f"{BASE}/{signal['id']}/approve", json={}, headers=auth_header(approver)
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == IntegritySignalStatus.APPROVED.value

    def test_cited_evidence_must_itself_have_been_approved(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = log_signal(client, monitor, organisation)
        draft = make_evidence(db, organisation, status=EvidenceStatus.DRAFT)
        assert assess(client, assessor, signal["id"], evidence_id=draft.id).status_code == 200

        response = client.post(
            f"{BASE}/{signal['id']}/approve", json={}, headers=auth_header(approver)
        )

        assert response.status_code == 409
        assert "has not been approved" in response.json()["detail"]

    def test_the_assessor_may_not_approve_their_own_finding(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        organisation: Organisation,
    ):
        """Separation of duties, with one person holding both roles."""
        both = member(db, organisation, Role.SUPER_ADMIN)
        signal = log_signal(client, both, organisation)
        evidence = approved_evidence(db, organisation)
        assert assess(client, both, signal["id"], evidence_id=evidence.id).status_code == 200

        response = client.post(f"{BASE}/{signal['id']}/approve", json={}, headers=auth_header(both))

        assert response.status_code == 403
        assert "Separation of duties" in response.json()["detail"]

    def test_approval_is_written_to_the_trail_with_the_version_reviewed(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        trail = client.get(f"{BASE}/{signal['id']}/approvals", headers=auth_header(approver)).json()

        assert len(trail) == 1
        assert trail[0]["decision"] == "approved"
        assert trail[0]["reviewer_id"] == str(approver.id)
        assert trail[0]["entity_version"] == signal["version"]

    def test_a_rejection_clears_the_approval_and_states_a_reason(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        response = client.post(
            f"{BASE}/{signal['id']}/reject",
            json={"comments": "The milestone records cited do not cover August."},
            headers=auth_header(approver),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == IntegritySignalStatus.ASSESSING.value
        assert body["approved_by"] is None

        trail = client.get(f"{BASE}/{signal['id']}/approvals", headers=auth_header(approver)).json()
        assert [entry["decision"] for entry in trail] == ["approved", "rejected"]

    def test_a_rejection_without_a_reason_is_refused(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        response = client.post(
            f"{BASE}/{signal['id']}/reject", json={"comments": ""}, headers=auth_header(approver)
        )

        assert response.status_code == 422


# --- Editing ---------------------------------------------------------------


class TestEditing:
    def test_rewording_the_claim_throws_away_the_finding(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        """The finding answered the old wording, so it cannot survive a rewrite."""
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        response = client.put(
            f"{BASE}/{signal['id']}",
            json={"claim": "The borehole programme in Bida was suspended, not cancelled."},
            headers=auth_header(monitor),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["finding"] is None
        assert body["assessed_by"] is None
        assert body["approved_by"] is None
        assert body["status"] == IntegritySignalStatus.ASSESSING.value
        assert body["version"] == signal["version"] + 1

    def test_reprioritising_does_not_throw_away_the_finding(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        response = client.put(
            f"{BASE}/{signal['id']}",
            json={"priority": IntegritySignalPriority.CRISIS.value},
            headers=auth_header(monitor),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["priority"] == IntegritySignalPriority.CRISIS.value
        assert body["finding"] == IntegrityFinding.FALSE.value
        assert body["status"] == IntegritySignalStatus.APPROVED.value


# --- Publication -----------------------------------------------------------


class TestPublication:
    def test_the_approver_may_not_publish_what_they_approved(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        organisation: Organisation,
    ):
        both = member(db, organisation, Role.SUPER_ADMIN)
        signal = take_to_approved(client, db, organisation, assessor, both, monitor)

        response = client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(both))

        assert response.status_code == 403
        assert "Separation of duties" in response.json()["detail"]

    def test_a_publisher_releases_the_correction(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        response = client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == IntegritySignalStatus.PUBLISHED.value
        assert body["published_at"] is not None

    def test_evidence_withdrawn_after_approval_stops_publication(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        """Re-checked at publication because it can change in between."""
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        record = db.get(IntegritySignal, uuid.UUID(signal["id"]))
        evidence = db.get(Evidence, record.evidence_id)
        evidence.status = EvidenceStatus.ARCHIVED
        db.commit()

        response = client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))

        assert response.status_code == 409

    def test_an_unapproved_finding_cannot_be_published(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = log_signal(client, monitor, organisation)
        evidence = approved_evidence(db, organisation)
        assert assess(client, assessor, signal["id"], evidence_id=evidence.id).status_code == 200

        response = client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))

        assert response.status_code == 409

    def test_a_published_correction_cannot_be_edited(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)
        assert (
            client.post(
                f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher)
            ).status_code
            == 200
        )

        response = client.put(
            f"{BASE}/{signal['id']}",
            json={"claim": "Something else entirely."},
            headers=auth_header(monitor),
        )

        assert response.status_code == 409

    def test_a_published_correction_is_withdrawn_rather_than_closed(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)
        client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))

        closed = client.post(f"{BASE}/{signal['id']}/close", headers=auth_header(monitor))
        assert closed.status_code == 409

        withdrawn = client.post(
            f"{BASE}/{signal['id']}/withdraw",
            json={"reason": "The milestone records were misread."},
            headers=auth_header(publisher),
        )
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == IntegritySignalStatus.WITHDRAWN.value

    def test_withdrawal_records_the_stated_reason(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)
        client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))
        client.post(
            f"{BASE}/{signal['id']}/withdraw",
            json={"reason": "The milestone records were misread."},
            headers=auth_header(publisher),
        )

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == uuid.UUID(signal["id"]),
                AuditLog.action == "withdrawn",
            )
            .one()
        )
        assert entry.new_values["reason"] == "The milestone records were misread."


# --- Tenancy ---------------------------------------------------------------


class TestTenancy:
    def test_another_body_cannot_read_a_signal(
        self,
        client: TestClient,
        monitor: User,
        outsider: User,
        organisation: Organisation,
    ):
        signal = log_signal(client, monitor, organisation)

        response = client.get(f"{BASE}/{signal['id']}", headers=auth_header(outsider))

        assert response.status_code == 404

    def test_listing_shows_only_the_caller_s_organisations(
        self,
        client: TestClient,
        monitor: User,
        outsider: User,
        organisation: Organisation,
    ):
        log_signal(client, monitor, organisation)

        response = client.get(f"{BASE}/", headers=auth_header(outsider))

        assert response.status_code == 200
        assert response.json()["total"] == 0


# --- The public record -----------------------------------------------------


class TestPublicRecord:
    def test_only_published_corrections_reach_the_portal(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        before = client.get("/api/v1/public/corrections").json()
        assert before["total"] == 0

        client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))

        after = client.get("/api/v1/public/corrections").json()
        assert after["total"] == 1
        assert after["data"][0]["claim"] == CLAIM

    def test_the_portal_publishes_the_reasoning_not_only_the_verdict(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        """A correction the public cannot check is an assertion, not evidence."""
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)
        client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))

        published = client.get(f"/api/v1/public/corrections/{signal['id']}").json()

        assert published["finding"] == IntegrityFinding.FALSE.value
        assert published["assessment"]
        assert published["evidence_reference"]

    def test_a_withdrawn_correction_leaves_the_portal(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        publisher: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)
        client.post(f"{BASE}/{signal['id']}/publish", headers=auth_header(publisher))
        client.post(
            f"{BASE}/{signal['id']}/withdraw",
            json={"reason": "Misread."},
            headers=auth_header(publisher),
        )

        assert client.get(f"/api/v1/public/corrections/{signal['id']}").status_code == 404
        assert client.get("/api/v1/public/corrections").json()["total"] == 0

    def test_an_unpublished_correction_is_reported_missing_not_forbidden(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        assessor: User,
        approver: User,
        organisation: Organisation,
    ):
        signal = take_to_approved(client, db, organisation, assessor, approver, monitor)

        response = client.get(f"/api/v1/public/corrections/{signal['id']}")

        assert response.status_code == 404

    def test_the_public_shape_identifies_nobody(self):
        """Spec sections 4 and 20, asserted against the schema itself.

        A field naming a reviewer would be a disclosure; a field naming whoever
        repeated the claim would be the profiling section 4 forbids. Neither
        can appear without this failing.
        """
        fields = set(PublicCorrection.model_fields)

        assert fields == {
            "id",
            "claim",
            "finding",
            "assessment",
            "response",
            "source",
            "first_observed",
            "published_at",
            "language",
            "evidence_reference",
            "organisation",
        }

    def test_the_model_has_nowhere_to_record_who_spread_a_claim(self):
        """The prohibition is structural, not a matter of remembering."""
        columns = set(IntegritySignal.__table__.columns.keys())

        forbidden = {
            "spreader",
            "spreader_id",
            "account",
            "account_handle",
            "poster",
            "audience",
            "audience_segment",
            "demographic",
            "political_affiliation",
            "susceptibility_score",
        }
        assert columns & forbidden == set()


# --- Search ----------------------------------------------------------------


class TestSearch:
    def test_a_signal_is_findable_by_its_claim(
        self, client: TestClient, monitor: User, organisation: Organisation
    ):
        log_signal(client, monitor, organisation, claim="Fertiliser vouchers were withdrawn.")

        response = client.get(
            "/api/v1/search/", params={"q": "fertiliser"}, headers=auth_header(monitor)
        )

        assert response.status_code == 200, response.text
        results = response.json()["integrity_signals"]
        assert len(results) == 1
        assert "Fertiliser" in results[0]["claim"]

    def test_a_source_filtered_search_excludes_signals(
        self,
        client: TestClient,
        db: Session,
        monitor: User,
        organisation: Organisation,
    ):
        """A channel is prose, not an entry in the source registry.

        Returning signals unfiltered would read as though the filter had
        matched them.
        """
        log_signal(client, monitor, organisation, claim="Fertiliser vouchers were withdrawn.")
        evidence = approved_evidence(db, organisation)

        response = client.get(
            "/api/v1/search/",
            params={"q": "fertiliser", "source_id": str(evidence.source_id)},
            headers=auth_header(monitor),
        )

        assert response.status_code == 200
        assert response.json()["integrity_signals"] == []
