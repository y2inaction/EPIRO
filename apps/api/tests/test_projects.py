"""Project and programme tests.

Covers spec section 12 (the seven-state lifecycle, milestones, indicators) and
the completion rule from section 51.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    GeographyLevel,
    Organisation,
    Programme,
    Project,
    ProjectStatus,
    Role,
    User,
)
from tests.conftest import auth_header, make_area, make_area_chain, make_evidence, member


def make_project(db: Session, organisation: Organisation, **overrides) -> Project:
    """Create a persisted project."""
    fields = {
        "organisation_id": organisation.id,
        "name": f"Project {uuid.uuid4().hex[:8]}",
        "code": f"prj-{uuid.uuid4().hex[:8]}",
        "status": ProjectStatus.ACTIVE,
    }
    fields.update(overrides)

    project = Project(**fields)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


class TestLifecycle:
    def test_a_project_starts_proposed(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        editor = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            "/api/v1/projects/",
            json={
                "organisation_id": str(organisation.id),
                "name": "Rural water scheme",
                "code": "rws-1",
            },
            headers=auth_header(editor),
        )
        assert response.status_code == 201
        assert response.json()["status"] == "proposed"

    def test_completion_requires_an_actual_completion_date(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Spec section 51: completion must carry the information that checks it."""
        project = make_project(db, organisation)
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"/api/v1/projects/{project.id}/status",
            json={"status": "completed"},
            headers=auth_header(manager),
        )
        assert response.status_code == 409

        db.refresh(project)
        assert project.status is ProjectStatus.ACTIVE

    def test_completion_succeeds_with_a_date(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        project = make_project(db, organisation, start_date="2026-01-01")
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"/api/v1/projects/{project.id}/status",
            json={"status": "completed", "actual_completion": "2026-06-30"},
            headers=auth_header(manager),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["actual_completion"] == "2026-06-30"

    def test_completion_cannot_predate_the_start(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        project = make_project(db, organisation, start_date="2026-05-01")
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"/api/v1/projects/{project.id}/status",
            json={"status": "completed", "actual_completion": "2026-01-01"},
            headers=auth_header(manager),
        )
        assert response.status_code == 400

    def test_an_archived_project_cannot_be_reopened(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The archived record must stay as it was."""
        project = make_project(db, organisation, status=ProjectStatus.ARCHIVED)
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"/api/v1/projects/{project.id}/status",
            json={"status": "active"},
            headers=auth_header(manager),
        )
        assert response.status_code == 409

    def test_a_field_officer_cannot_change_the_lifecycle(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Declaring a project complete is a management decision."""
        project = make_project(db, organisation)
        officer = member(db, organisation, Role.FIELD_OFFICER)

        response = client.post(
            f"/api/v1/projects/{project.id}/status",
            json={"status": "delayed"},
            headers=auth_header(officer),
        )
        assert response.status_code == 403

    def test_a_field_officer_can_record_project_detail(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        project = make_project(db, organisation)
        officer = member(db, organisation, Role.FIELD_OFFICER)

        response = client.put(
            f"/api/v1/projects/{project.id}",
            json={"description": "Observed on site: three boreholes sunk."},
            headers=auth_header(officer),
        )
        assert response.status_code == 200


class TestReferences:
    def test_a_programme_from_another_organisation_is_rejected(
        self,
        client: TestClient,
        db: Session,
        organisation: Organisation,
        other_organisation: Organisation,
    ):
        foreign = Programme(organisation_id=other_organisation.id, name="Foreign", code="foreign-1")
        db.add(foreign)
        db.commit()

        editor = member(db, organisation, Role.EVIDENCE_MANAGER)
        response = client.post(
            "/api/v1/projects/",
            json={
                "organisation_id": str(organisation.id),
                "name": "Cross tenant",
                "code": "cross-1",
                "programme_id": str(foreign.id),
            },
            headers=auth_header(editor),
        )
        assert response.status_code == 400

    def test_a_duplicate_code_within_an_organisation_is_rejected(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_project(db, organisation, code="duplicate-1")
        editor = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            "/api/v1/projects/",
            json={
                "organisation_id": str(organisation.id),
                "name": "Second",
                "code": "duplicate-1",
            },
            headers=auth_header(editor),
        )
        assert response.status_code == 400


class TestGeographicFiltering:
    def test_filtering_by_a_state_includes_projects_in_its_lgas(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Otherwise the hierarchy is decorative."""
        chain = make_area_chain(db)
        make_project(db, organisation, geography_id=chain["lga"].id)
        reader = member(db, organisation, Role.RESEARCHER)

        response = client.get(
            "/api/v1/projects/",
            params={"geography_id": str(chain["state"].id)},
            headers=auth_header(reader),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_filtering_by_an_unrelated_area_excludes_the_project(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        chain = make_area_chain(db)
        make_project(db, organisation, geography_id=chain["lga"].id)
        elsewhere = make_area(db, GeographyLevel.COUNTRY)
        reader = member(db, organisation, Role.RESEARCHER)

        response = client.get(
            "/api/v1/projects/",
            params={"geography_id": str(elsewhere.id)},
            headers=auth_header(reader),
        )
        assert response.json()["total"] == 0


class TestMilestonesAndIndicators:
    def test_milestones_are_returned_in_sequence(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        project = make_project(db, organisation)
        editor = member(db, organisation, Role.EVIDENCE_MANAGER)

        for title, sequence in (("Second", 2), ("First", 1)):
            client.post(
                f"/api/v1/projects/{project.id}/milestones",
                json={"title": title, "sequence": sequence},
                headers=auth_header(editor),
            )

        response = client.get(
            f"/api/v1/projects/{project.id}/milestones", headers=auth_header(editor)
        )
        assert response.status_code == 200
        assert [item["title"] for item in response.json()] == ["First", "Second"]

    def test_a_milestone_starts_pending(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        project = make_project(db, organisation)
        editor = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"/api/v1/projects/{project.id}/milestones",
            json={"title": "Site handover", "due_date": "2026-09-01"},
            headers=auth_header(editor),
        )
        assert response.status_code == 201
        assert response.json()["status"] == "pending"

    def test_a_milestone_from_another_project_is_not_reachable(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        first = make_project(db, organisation)
        second = make_project(db, organisation)
        editor = member(db, organisation, Role.EVIDENCE_MANAGER)

        created = client.post(
            f"/api/v1/projects/{first.id}/milestones",
            json={"title": "Belongs to first"},
            headers=auth_header(editor),
        ).json()

        response = client.put(
            f"/api/v1/projects/{second.id}/milestones/{created['id']}",
            json={"title": "Hijacked"},
            headers=auth_header(editor),
        )
        assert response.status_code == 404

    def test_an_indicator_carries_its_baseline_and_target(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        project = make_project(db, organisation)
        editor = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"/api/v1/projects/{project.id}/indicators",
            json={
                "organisation_id": str(organisation.id),
                "name": "Households with piped water",
                "unit": "households",
                "baseline_value": "1200",
                "target_value": "5000",
            },
            headers=auth_header(editor),
        )
        assert response.status_code == 201

        body = response.json()
        assert body["baseline_value"] == "1200.0000"
        assert body["target_value"] == "5000.0000"
        assert body["current_value"] is None


class TestDeletion:
    def test_a_project_cited_by_evidence_cannot_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Archiving keeps the record of what was done."""
        project = make_project(db, organisation)
        make_evidence(db, organisation, project_id=project.id)
        manager = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.delete(f"/api/v1/projects/{project.id}", headers=auth_header(manager))
        assert response.status_code == 409

    def test_a_programme_holding_projects_cannot_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        programme = Programme(organisation_id=organisation.id, name="Water", code="water-1")
        db.add(programme)
        db.commit()
        make_project(db, organisation, programme_id=programme.id)

        manager = member(db, organisation, Role.EVIDENCE_MANAGER)
        response = client.delete(f"/api/v1/programmes/{programme.id}", headers=auth_header(manager))
        assert response.status_code == 409


class TestTenantIsolation:
    def test_another_tenant_cannot_read_a_project(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        project = make_project(db, organisation)

        response = client.get(f"/api/v1/projects/{project.id}", headers=auth_header(outsider))
        assert response.status_code == 404

    def test_another_tenant_cannot_change_a_project_status(
        self, client: TestClient, db: Session, organisation: Organisation, outsider: User
    ):
        project = make_project(db, organisation)

        response = client.post(
            f"/api/v1/projects/{project.id}/status",
            json={"status": "suspended"},
            headers=auth_header(outsider),
        )
        assert response.status_code == 404
