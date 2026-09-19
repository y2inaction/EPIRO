"""Source registry tests.

Covers spec section 11: transparent verification states, a reliability
classification that must be justified, and provenance that cannot be quietly
detached from evidence.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Organisation, Role, Source, SourceReliability, User, VerificationState
from tests.conftest import auth_header, make_evidence, make_source, member


class TestRegistration:
    def test_a_source_starts_unverified(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Nothing is trusted on arrival (spec section 11)."""
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/sources/",
            json={
                "organisation_id": str(organisation.id),
                "name": "National budget implementation report",
                "source_type": "government_data",
                "publisher": "Budget Office",
                "author": "Statistics Division",
            },
            headers=auth_header(author),
        )
        assert response.status_code == 201

        body = response.json()
        assert body["verification_state"] == "unverified"
        assert body["reliability"] == "unknown"

    def test_an_unknown_source_type_is_rejected(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/sources/",
            json={
                "organisation_id": str(organisation.id),
                "name": "Hearsay",
                "source_type": "rumour",
            },
            headers=auth_header(author),
        )
        assert response.status_code == 422


class TestReview:
    def test_a_verifier_records_a_decision_with_a_rationale(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)

        response = client.post(
            f"/api/v1/sources/{source.id}/review",
            json={
                "verification_state": "verified",
                "reliability": "high",
                "rationale": "Primary document obtained directly from the issuing body.",
            },
            headers=auth_header(verifier),
        )
        assert response.status_code == 200

        body = response.json()
        assert body["verification_state"] == "verified"
        assert body["reliability"] == "high"
        assert body["reviewed_by"] == str(verifier.id)
        assert body["review_date"] is not None

    def test_a_classification_without_a_rationale_is_rejected(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """An unexplained reliability score is what spec section 7 rules out."""
        source = make_source(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)

        response = client.post(
            f"/api/v1/sources/{source.id}/review",
            json={"verification_state": "verified", "reliability": "high"},
            headers=auth_header(verifier),
        )
        assert response.status_code == 422

    def test_a_researcher_cannot_verify_a_source(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/sources/{source.id}/review",
            json={
                "verification_state": "verified",
                "reliability": "high",
                "rationale": "Trust me.",
            },
            headers=auth_header(researcher),
        )
        assert response.status_code == 403

        db.refresh(source)
        assert source.verification_state is VerificationState.UNVERIFIED

    def test_disputed_is_available_as_an_outcome(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Review can conclude doubt, not only pass or fail."""
        source = make_source(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)

        response = client.post(
            f"/api/v1/sources/{source.id}/review",
            json={
                "verification_state": "disputed",
                "reliability": "low",
                "rationale": "The figures conflict with the published dataset.",
            },
            headers=auth_header(verifier),
        )
        assert response.status_code == 200
        assert response.json()["verification_state"] == "disputed"


class TestReviewInvalidation:
    def test_changing_the_document_resets_the_verification(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A review applies to what was reviewed, not to whatever replaces it."""
        source = make_source(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)
        author = member(db, organisation, Role.RESEARCHER)

        client.post(
            f"/api/v1/sources/{source.id}/review",
            json={
                "verification_state": "verified",
                "reliability": "high",
                "rationale": "Checked against the original.",
            },
            headers=auth_header(verifier),
        )

        response = client.put(
            f"/api/v1/sources/{source.id}",
            json={"document_url": "https://example.com/a-different-document.pdf"},
            headers=auth_header(author),
        )
        assert response.status_code == 200
        assert response.json()["verification_state"] == "unverified"

    def test_editing_a_description_does_not_reset_the_verification(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)
        author = member(db, organisation, Role.RESEARCHER)

        client.post(
            f"/api/v1/sources/{source.id}/review",
            json={
                "verification_state": "verified",
                "reliability": "moderate",
                "rationale": "Corroborated by a second source.",
            },
            headers=auth_header(verifier),
        )

        response = client.put(
            f"/api/v1/sources/{source.id}",
            json={"description": "Clarified wording"},
            headers=auth_header(author),
        )
        assert response.status_code == 200
        assert response.json()["verification_state"] == "verified"


class TestProvenanceIntegrity:
    def test_a_cited_source_cannot_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Deleting it would make the evidence citing it untraceable."""
        source = make_source(db, organisation)
        make_evidence(db, organisation, source=source)
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.delete(f"/api/v1/sources/{source.id}", headers=auth_header(manager))
        assert response.status_code == 409

        db.refresh(source)
        assert source.id is not None

    def test_an_uncited_source_can_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.delete(f"/api/v1/sources/{source.id}", headers=auth_header(manager))
        assert response.status_code == 200
        assert db.get(Source, source.id) is None


class TestTenantIsolation:
    def test_another_tenant_cannot_read_a_source(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        source = make_source(db, organisation)

        response = client.get(f"/api/v1/sources/{source.id}", headers=auth_header(outsider))
        assert response.status_code == 404

    def test_listing_is_scoped_to_the_callers_organisations(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        make_source(db, organisation)

        response = client.get("/api/v1/sources/", headers=auth_header(outsider))
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestReviewScheduling:
    def test_sources_due_for_review_can_be_listed(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A source verified long ago is not thereby still verified."""
        source = make_source(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)

        client.post(
            f"/api/v1/sources/{source.id}/review",
            json={
                "verification_state": "verified",
                "reliability": "high",
                "rationale": "Current at the time of review.",
                "next_review_date": "2020-01-01",
            },
            headers=auth_header(verifier),
        )

        response = client.get(
            "/api/v1/sources/",
            params={"due_for_review": "true"},
            headers=auth_header(verifier),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_reliability_defaults_to_unknown(self, db: Session, organisation: Organisation):
        source = make_source(db, organisation)
        assert source.reliability is SourceReliability.UNKNOWN
