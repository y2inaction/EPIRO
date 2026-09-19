"""Geographic hierarchy tests.

Covers spec section 13: the Country / Region / State / LGA / Ward / Community
tree that replaced the flat location strings.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Geography, GeographyLevel, Organisation, Project, ProjectStatus, Role
from app.services.geography import ancestors, descendant_ids
from tests.conftest import auth_header, make_area, make_area_chain, make_platform_admin, member


class TestHierarchyRules:
    """A node's parent must sit above it, and levels may be skipped."""

    def test_a_state_may_be_created_under_a_country(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        admin = make_platform_admin(db)
        country = make_area(db, GeographyLevel.COUNTRY)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Niger", "level": "state", "parent_id": str(country.id)},
            headers=auth_header(admin),
        )
        assert response.status_code == 201
        assert response.json()["level"] == "state"

    def test_a_state_may_skip_the_region_tier(self, client: TestClient, db: Session):
        """Not every country has a region layer between country and state."""
        admin = make_platform_admin(db)
        country = make_area(db, GeographyLevel.COUNTRY)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Skips region", "level": "state", "parent_id": str(country.id)},
            headers=auth_header(admin),
        )
        assert response.status_code == 201

    def test_a_state_cannot_sit_under_an_lga(self, client: TestClient, db: Session):
        """An inverted tree would make every roll-up meaningless."""
        admin = make_platform_admin(db)
        chain = make_area_chain(db)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Inverted", "level": "state", "parent_id": str(chain["lga"].id)},
            headers=auth_header(admin),
        )
        assert response.status_code == 400

    def test_a_node_cannot_be_its_own_level_parent(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)
        chain = make_area_chain(db)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Sibling", "level": "state", "parent_id": str(chain["state"].id)},
            headers=auth_header(admin),
        )
        assert response.status_code == 400

    def test_only_a_country_may_have_no_parent(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Orphan state", "level": "state"},
            headers=auth_header(admin),
        )
        assert response.status_code == 400

    def test_a_country_may_be_created_without_a_parent(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Nigeria", "level": "country", "code": "NG"},
            headers=auth_header(admin),
        )
        assert response.status_code == 201
        assert response.json()["parent_id"] is None

    def test_an_unknown_parent_is_reported(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Nowhere", "level": "state", "parent_id": str(uuid.uuid4())},
            headers=auth_header(admin),
        )
        assert response.status_code == 404


class TestTreeQueries:
    def test_ancestors_run_from_nearest_parent_to_country(self, db: Session):
        chain = make_area_chain(db)

        result = ancestors(db, chain["lga"].id)

        assert [node.id for node in result] == [chain["state"].id, chain["country"].id]

    def test_descendants_include_the_root_and_everything_below(self, db: Session):
        chain = make_area_chain(db)

        result = set(descendant_ids(db, chain["country"].id))

        assert result == {chain["country"].id, chain["state"].id, chain["lga"].id}

    def test_descendants_of_a_leaf_are_just_the_leaf(self, db: Session):
        chain = make_area_chain(db)

        assert descendant_ids(db, chain["lga"].id) == [chain["lga"].id]

    def test_children_lists_only_the_immediate_tier(self, client: TestClient, db: Session):
        chain = make_area_chain(db)
        reader = make_platform_admin(db)

        response = client.get(
            f"/api/v1/geography/{chain['country'].id}/children", headers=auth_header(reader)
        )
        assert response.status_code == 200

        returned = [item["id"] for item in response.json()]
        assert returned == [str(chain["state"].id)]


class TestAccess:
    def test_reference_data_is_readable_by_any_member(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The map is shared, so a plain member may read it."""
        make_area(db, GeographyLevel.COUNTRY)
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.get("/api/v1/geography/", headers=auth_header(researcher))
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_creating_an_area_requires_a_platform_admin(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A tenant must not be able to edit shared reference data."""
        owner = member(db, organisation, Role.SUPER_ADMIN)

        response = client.post(
            "/api/v1/geography/",
            json={"name": "Unauthorised", "level": "country"},
            headers=auth_header(owner),
        )
        assert response.status_code == 403

    def test_listing_requires_authentication(self, client: TestClient):
        assert client.get("/api/v1/geography/").status_code == 401


class TestDeletion:
    def test_an_area_with_children_cannot_be_deleted(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)
        chain = make_area_chain(db)

        response = client.delete(
            f"/api/v1/geography/{chain['country'].id}", headers=auth_header(admin)
        )
        assert response.status_code == 409

    def test_an_area_in_use_by_a_project_cannot_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Deleting it would leave the project unplaceable on a map."""
        admin = make_platform_admin(db)
        area = make_area(db, GeographyLevel.COUNTRY)
        db.add(
            Project(
                organisation_id=organisation.id,
                name="Sited project",
                code="sited-1",
                status=ProjectStatus.ACTIVE,
                geography_id=area.id,
            )
        )
        db.commit()

        response = client.delete(f"/api/v1/geography/{area.id}", headers=auth_header(admin))
        assert response.status_code == 409

    def test_an_unused_leaf_can_be_deleted(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)
        area = make_area(db, GeographyLevel.COUNTRY)

        response = client.delete(f"/api/v1/geography/{area.id}", headers=auth_header(admin))
        assert response.status_code == 200
        assert db.get(Geography, area.id) is None
