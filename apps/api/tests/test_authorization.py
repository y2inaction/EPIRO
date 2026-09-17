"""Authorization tests.

These cover the defects recorded in docs/REBUILD_AUDIT.md section 4: the
no-op admin dependency, ungated workflow transitions, mass assignment through
untyped bodies, and the absence of tenant isolation.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EvidenceStatus, Organisation, Role, User
from tests.conftest import (
    auth_header,
    grant_role,
    make_evidence,
    make_organisation,
    make_source,
    make_story,
    make_user,
    member,
)


class TestAuthenticationRequired:
    """Protected endpoints must reject anonymous callers."""

    def test_listing_evidence_requires_authentication(self, client: TestClient):
        response = client.get("/api/v1/evidence/", params={"organisation_id": str(uuid.uuid4())})
        assert response.status_code == 401

    def test_listing_users_requires_authentication(self, client: TestClient):
        assert client.get("/api/v1/users/").status_code == 401

    def test_refresh_token_is_rejected_as_an_access_token(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A refresh token has a far longer life and must not authenticate."""
        from app.security import create_refresh_token

        user = member(db, organisation, Role.RESEARCHER)
        refresh = create_refresh_token(str(user.id))

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {refresh}"})
        assert response.status_code == 401


class TestTenantIsolation:
    """A caller must not reach another organisation's data."""

    def test_cannot_read_evidence_of_another_organisation(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        evidence = make_evidence(db, organisation)

        response = client.get(f"/api/v1/evidence/{evidence.id}", headers=auth_header(outsider))
        # Reported as missing rather than forbidden, so the endpoint does not
        # confirm the id exists in another tenant.
        assert response.status_code == 404

    def test_cannot_list_evidence_of_another_organisation(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        make_evidence(db, organisation)

        response = client.get(
            "/api/v1/evidence/",
            params={"organisation_id": str(organisation.id)},
            headers=auth_header(outsider),
        )
        assert response.status_code == 403

    def test_cannot_delete_evidence_of_another_organisation(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        evidence = make_evidence(db, organisation)

        response = client.delete(f"/api/v1/evidence/{evidence.id}", headers=auth_header(outsider))
        assert response.status_code == 404

        db.refresh(evidence)
        assert evidence.id is not None

    def test_search_does_not_return_other_tenants_content(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole rehabilitation programme")

        stranger = member(db, make_organisation(db), Role.RESEARCHER)

        response = client.get(
            "/api/v1/search/", params={"q": "Borehole"}, headers=auth_header(stranger)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["evidence"] == []
        assert body["total"] == 0

    def test_evidence_cannot_cite_a_source_from_another_organisation(
        self,
        client: TestClient,
        db: Session,
        organisation: Organisation,
        other_organisation: Organisation,
    ):
        author = member(db, organisation, Role.RESEARCHER)
        foreign_source = make_source(db, other_organisation)

        response = client.post(
            "/api/v1/evidence/",
            json={
                "title": "Cross tenant provenance",
                "organisation_id": str(organisation.id),
                "source_id": str(foreign_source.id),
            },
            headers=auth_header(author),
        )
        assert response.status_code == 400


class TestRoleEnforcement:
    """Workflow transitions require the matching role."""

    def test_researcher_cannot_verify_evidence(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(researcher)
        )
        assert response.status_code == 403

        db.refresh(evidence)
        assert evidence.verification_status == "unverified"

    def test_verifier_can_verify_evidence(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(verifier)
        )
        assert response.status_code == 200
        assert response.json()["verification_status"] == "verified"

    def test_a_plain_member_cannot_delete_an_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.delete(
            f"/api/v1/organisations/{organisation.id}", headers=auth_header(researcher)
        )
        assert response.status_code == 403

    def test_a_plain_member_cannot_list_all_users(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.get("/api/v1/users/", headers=auth_header(researcher))
        assert response.status_code == 403

    def test_a_user_cannot_update_another_user(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        researcher = member(db, organisation, Role.RESEARCHER)
        victim = make_user(db)

        response = client.put(
            f"/api/v1/users/{victim.id}",
            json={"first_name": "Renamed"},
            headers=auth_header(researcher),
        )
        assert response.status_code == 403

        db.refresh(victim)
        assert victim.first_name == "Test"

    def test_a_user_cannot_deactivate_another_user(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        researcher = member(db, organisation, Role.RESEARCHER)
        victim = make_user(db)

        response = client.post(
            f"/api/v1/users/{victim.id}/deactivate", headers=auth_header(researcher)
        )
        assert response.status_code == 403

        db.refresh(victim)
        assert victim.is_active is True


class TestSeparationOfDuties:
    """A single person must not carry a record through two approval gates."""

    def test_approval_requires_verification_first(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )
        assert response.status_code == 409

    def test_the_verifier_cannot_also_approve(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Holding every right in an organisation is not enough to do both steps."""
        evidence = make_evidence(db, organisation)
        both = make_user(db)
        grant_role(db, both, organisation, Role.SUPER_ADMIN)

        verify = client.post(f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(both))
        assert verify.status_code == 200

        approve = client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(both))
        assert approve.status_code == 403

        db.refresh(evidence)
        assert evidence.approval_status == "pending"

    def test_a_different_approver_can_approve_verified_evidence(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)
        approver = member(db, organisation, Role.APPROVER)

        client.post(f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(verifier))
        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 200
        assert response.json()["approval_status"] == "approved"

    def test_publishing_requires_approval(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/publish", headers=auth_header(publisher)
        )
        assert response.status_code == 409

        db.refresh(evidence)
        assert evidence.status == EvidenceStatus.DRAFT


class TestMassAssignment:
    """Workflow state must not be reachable through a general update."""

    def test_update_cannot_set_approval_state(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        author = member(db, organisation, Role.RESEARCHER)

        response = client.put(
            f"/api/v1/evidence/{evidence.id}",
            json={
                "title": "Legitimate edit",
                "approval_status": "approved",
                "verification_status": "verified",
                "status": "published",
            },
            headers=auth_header(author),
        )
        assert response.status_code == 200

        db.refresh(evidence)
        assert evidence.title == "Legitimate edit"
        # The smuggled workflow fields were not applied.
        assert evidence.approval_status == "pending"
        assert evidence.verification_status == "unverified"
        assert evidence.status == EvidenceStatus.DRAFT


class TestPublicationGate:
    """Public information must trace back to approved evidence."""

    def test_story_cannot_be_published_while_evidence_is_unapproved(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        story = make_story(db, evidence)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/stories/{story.id}/publish", headers=auth_header(publisher)
        )
        assert response.status_code == 409

        db.refresh(story)
        assert story.status == "draft"

    def test_story_publishes_once_evidence_is_approved(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.APPROVED)
        story = make_story(db, evidence)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/stories/{story.id}/publish", headers=auth_header(publisher)
        )
        assert response.status_code == 200
        assert response.json()["status"] == "published"
