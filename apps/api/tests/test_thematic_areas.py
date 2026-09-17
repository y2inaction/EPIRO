"""Thematic taxonomy tests.

Covers spec section 9 (eight streams, configurable rather than hard-coded) and
section 56 (seeds must be repeatable and idempotent).
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Evidence, Organisation, Role, ThematicArea
from app.services.seed import THEMATIC_STREAMS, seed_thematic_areas
from tests.conftest import auth_header, make_evidence, make_platform_admin, member


class TestSeeding:
    def test_seeding_creates_the_eight_streams(self, db: Session):
        areas = seed_thematic_areas(db)

        assert len(areas) == 8
        assert {area.code for area in areas} == {code for code, _, _ in THEMATIC_STREAMS}

    def test_seeding_twice_does_not_duplicate(self, db: Session):
        """Spec section 56: a seed must be safe to run again."""
        seed_thematic_areas(db)
        seed_thematic_areas(db)

        assert db.query(ThematicArea).count() == 8

    def test_seeding_again_keeps_existing_ids(self, db: Session):
        """Evidence references these rows, so the ids must be stable."""
        before = {area.code: area.id for area in seed_thematic_areas(db)}
        after = {area.code: area.id for area in seed_thematic_areas(db)}

        assert before == after

    def test_seeding_does_not_reactivate_a_disabled_stream(self, db: Session):
        """A deliberately disabled stream must not come back on the next run."""
        areas = seed_thematic_areas(db)
        areas[0].is_active = False
        db.commit()

        seed_thematic_areas(db)

        db.refresh(areas[0])
        assert areas[0].is_active is False


class TestTaxonomyIsConfigurable:
    def test_an_administrator_can_add_a_ninth_stream(self, client: TestClient, db: Session):
        """Section 9 requires the taxonomy not be hard-coded."""
        seed_thematic_areas(db)
        admin = make_platform_admin(db)

        response = client.post(
            "/api/v1/thematic-areas/",
            json={
                "name": "Climate Resilience",
                "code": "climate-resilience",
                "description": "Adaptation, flooding and drought response.",
            },
            headers=auth_header(admin),
        )
        assert response.status_code == 201
        assert db.query(ThematicArea).count() == 9

    def test_a_duplicate_code_is_rejected(self, client: TestClient, db: Session):
        seed_thematic_areas(db)
        admin = make_platform_admin(db)

        response = client.post(
            "/api/v1/thematic-areas/",
            json={"name": "Duplicate", "code": "agriculture"},
            headers=auth_header(admin),
        )
        assert response.status_code == 400

    def test_an_invalid_colour_is_rejected(self, client: TestClient, db: Session):
        admin = make_platform_admin(db)

        response = client.post(
            "/api/v1/thematic-areas/",
            json={"name": "Bad colour", "code": "bad-colour", "color": "red"},
            headers=auth_header(admin),
        )
        assert response.status_code == 422


class TestAccess:
    def test_any_member_can_read_the_taxonomy(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        seed_thematic_areas(db)
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.get("/api/v1/thematic-areas/", headers=auth_header(researcher))
        assert response.status_code == 200
        assert response.json()["total"] == 8

    def test_a_tenant_admin_cannot_change_shared_reference_data(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        owner = member(db, organisation, Role.SUPER_ADMIN)

        response = client.post(
            "/api/v1/thematic-areas/",
            json={"name": "Unauthorised", "code": "unauthorised"},
            headers=auth_header(owner),
        )
        assert response.status_code == 403

    def test_listing_requires_authentication(self, client: TestClient):
        assert client.get("/api/v1/thematic-areas/").status_code == 401

    def test_streams_are_returned_in_their_configured_order(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        seed_thematic_areas(db)
        researcher = member(db, organisation, Role.RESEARCHER)

        response = client.get("/api/v1/thematic-areas/", headers=auth_header(researcher))
        returned = [item["code"] for item in response.json()["data"]]

        assert returned == [code for code, _, _ in THEMATIC_STREAMS]


class TestDeletion:
    def test_a_stream_in_use_cannot_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Deleting it would strip the classification from filed evidence."""
        areas = seed_thematic_areas(db)
        evidence = make_evidence(db, organisation)
        evidence.thematic_area_id = areas[0].id
        db.commit()

        admin = make_platform_admin(db)
        response = client.delete(
            f"/api/v1/thematic-areas/{areas[0].id}", headers=auth_header(admin)
        )
        assert response.status_code == 409
        assert db.get(ThematicArea, areas[0].id) is not None

    def test_an_unused_stream_can_be_deleted(self, client: TestClient, db: Session):
        areas = seed_thematic_areas(db)
        admin = make_platform_admin(db)

        response = client.delete(
            f"/api/v1/thematic-areas/{areas[0].id}", headers=auth_header(admin)
        )
        assert response.status_code == 200
        assert db.query(Evidence).count() == 0
        assert db.query(ThematicArea).count() == 7
