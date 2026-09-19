"""Configurable workflow tests.

Covers spec section 36. The most important tests here are the ones asserting
what an organisation *cannot* configure: the platform's guarantees must not be
switchable by the people they hold to account.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ApprovalRecord, EvidenceStatus, Organisation, Role, WorkflowDefinition
from tests.conftest import auth_header, make_evidence, make_organisation, member


def define(client: TestClient, admin, organisation: Organisation, stages, entity_type="evidence"):
    """Define a workflow, returning the response."""
    return client.post(
        "/api/v1/workflows/",
        json={
            "organisation_id": str(organisation.id),
            "entity_type": entity_type,
            "name": "Editorial review",
            "stages": stages,
        },
        headers=auth_header(admin),
    )


def stage(name, roles, distinct=True):
    return {"name": name, "required_roles": roles, "requires_distinct_actor": distinct}


def verify(client: TestClient, db: Session, organisation: Organisation, evidence_id):
    """Take a record through verification."""
    verifier = member(db, organisation, Role.VERIFIER)
    response = client.post(f"/api/v1/evidence/{evidence_id}/verify", headers=auth_header(verifier))
    assert response.status_code == 200
    return verifier


class TestGuaranteesCannotBeConfiguredAway:
    """An organisation may add rigour. It may not remove it."""

    def test_the_final_stage_must_require_a_different_person(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)

        response = define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"], distinct=False)],
        )

        assert response.status_code == 400
        assert "different person" in response.json()["detail"]
        assert db.query(WorkflowDefinition).count() == 0

    def test_a_workflow_with_no_stages_is_refused(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)

        response = define(client, admin, organisation, [])

        assert response.status_code == 422

    def test_a_stage_nobody_can_clear_is_refused(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)

        response = define(client, admin, organisation, [stage("Nowhere", [])])

        assert response.status_code == 422

    def test_an_unknown_role_is_refused(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)

        response = define(client, admin, organisation, [stage("Approval", ["wizard"])])

        assert response.status_code == 400
        assert "Unknown role" in response.json()["detail"]

    def test_the_public_cannot_be_made_a_reviewer(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Review is what the organisation is accountable for, not the public."""
        admin = member(db, organisation, Role.EXECUTIVE)

        response = define(client, admin, organisation, [stage("Approval", ["public_user"])])

        assert response.status_code == 400
        assert "member of the public" in response.json()["detail"]

    def test_the_final_stage_is_stored_as_requiring_a_distinct_actor(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Asked for or not, the stored row agrees with the guarantee."""
        admin = member(db, organisation, Role.EXECUTIVE)

        body = define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"], distinct=False), stage("Approval", ["approver"])],
        ).json()

        assert body["stages"][-1]["requires_distinct_actor"] is True


class TestDefining:
    def test_an_executive_can_define_a_workflow(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)

        response = define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        assert response.status_code == 201
        body = response.json()
        assert [s["name"] for s in body["stages"]] == ["Fact check", "Approval"]
        assert [s["position"] for s in body["stages"]] == [0, 1]

    def test_an_ordinary_member_cannot(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        researcher = member(db, organisation, Role.RESEARCHER)

        response = define(client, researcher, organisation, [stage("Approval", ["approver"])])

        assert response.status_code == 403

    def test_defining_again_replaces_the_active_one(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Two active definitions would make the applicable workflow ambiguous."""
        admin = member(db, organisation, Role.EXECUTIVE)

        define(client, admin, organisation, [stage("Approval", ["approver"])])
        define(client, admin, organisation, [stage("Compliance", ["executive"])])

        active = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.organisation_id == organisation.id,
                WorkflowDefinition.is_active.is_(True),
            )
            .all()
        )
        assert len(active) == 1
        assert active[0].stages[0].name == "Compliance"

    def test_the_superseded_definition_is_kept(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Approval records point at its stages; deleting it would break the trail."""
        admin = member(db, organisation, Role.EXECUTIVE)

        define(client, admin, organisation, [stage("Approval", ["approver"])])
        define(client, admin, organisation, [stage("Compliance", ["executive"])])

        assert db.query(WorkflowDefinition).count() == 2

    def test_another_organisation_cannot_define_yours(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        outsider = member(db, make_organisation(db), Role.EXECUTIVE)

        response = define(client, outsider, organisation, [stage("Approval", ["approver"])])

        assert response.status_code == 403


class TestStagedApproval:
    def test_clearing_one_stage_of_two_does_not_approve(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        checker = member(db, organisation, Role.VERIFIER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(checker)
        )

        assert response.status_code == 200
        assert response.json()["approval_status"] != "approved"

    def test_clearing_every_stage_approves(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        checker = member(db, organisation, Role.VERIFIER)
        approver = member(db, organisation, Role.APPROVER)

        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(checker))
        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 200
        assert response.json()["approval_status"] == "approved"
        assert response.json()["status"] == EvidenceStatus.APPROVED.value

    def test_a_stage_refuses_a_role_that_cannot_clear_it(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)

        # The approver holds APPROVERS, so the endpoint lets them in, but the
        # first stage is for a verifier.
        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 403
        assert "Fact check" in response.json()["detail"]

    def test_one_person_cannot_clear_two_consecutive_stages(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The point of stages is that more than one person looked."""
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["evidence_manager"]), stage("Approval", ["evidence_manager"])],
        )

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        first = client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(manager))
        assert first.status_code == 200

        second = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(manager)
        )
        assert second.status_code == 403

    def test_each_cleared_stage_is_named_on_the_trail(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        checker = member(db, organisation, Role.VERIFIER)
        approver = member(db, organisation, Role.APPROVER)

        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(checker))
        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver))

        records = (
            db.query(ApprovalRecord)
            .filter(ApprovalRecord.entity_id == evidence.id)
            .order_by(ApprovalRecord.decided_at)
            .all()
        )
        assert len(records) == 2
        assert all(record.workflow_stage_id is not None for record in records)

    def test_a_rejection_sends_the_record_back_to_the_first_stage(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Whatever was cleared was cleared against content since sent back."""
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        checker = member(db, organisation, Role.VERIFIER)
        approver = member(db, organisation, Role.APPROVER)

        client.post(f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(checker))
        client.post(
            f"/api/v1/evidence/{evidence.id}/reject",
            json={"comments": "The register reference is wrong."},
            headers=auth_header(approver),
        )

        # Back at the first stage, so the approver is refused again.
        verify(client, db, organisation, evidence.id)
        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 403
        assert "Fact check" in response.json()["detail"]


class TestWithoutAWorkflow:
    """Every organisation works exactly as before until it defines one."""

    def test_one_approval_still_approves(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 200
        assert response.json()["approval_status"] == "approved"

    def test_the_verifier_still_cannot_approve(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation)
        verifier = member(db, organisation, Role.VERIFIER)
        client.post(f"/api/v1/evidence/{evidence.id}/verify", headers=auth_header(verifier))

        # Give the same person the approver role too.
        from tests.conftest import grant_role

        other = make_organisation(db)
        grant_role(db, verifier, other, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(verifier)
        )

        assert response.status_code == 403

    def test_a_deactivated_workflow_returns_to_the_single_stage(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = member(db, organisation, Role.EXECUTIVE)
        created = define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        ).json()

        client.delete(f"/api/v1/workflows/{created['id']}", headers=auth_header(admin))

        evidence = make_evidence(db, organisation)
        verify(client, db, organisation, evidence.id)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 200
        assert response.json()["approval_status"] == "approved"


class TestTenancy:
    def test_another_organisations_workflow_is_not_listable(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        outsider = member(db, organisation, Role.EXECUTIVE)

        response = client.get(
            "/api/v1/workflows/",
            params={"organisation_id": str(other.id)},
            headers=auth_header(outsider),
        )

        assert response.status_code == 403

    def test_one_organisations_workflow_does_not_govern_another(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Definitions are per organisation, so a neighbour's stages do not apply."""
        admin = member(db, organisation, Role.EXECUTIVE)
        define(
            client,
            admin,
            organisation,
            [stage("Fact check", ["verifier"]), stage("Approval", ["approver"])],
        )

        other = make_organisation(db)
        evidence = make_evidence(db, other)
        verify(client, db, other, evidence.id)
        approver = member(db, other, Role.APPROVER)

        response = client.post(
            f"/api/v1/evidence/{evidence.id}/approve", headers=auth_header(approver)
        )

        assert response.status_code == 200
        assert response.json()["approval_status"] == "approved"
