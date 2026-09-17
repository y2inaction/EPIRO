"""Evidence registry completion tests.

Covers spec section 10: the permanent reference, the RESULT block linking
evidence to an indicator, and the rule that a reported figure traces back to
an approved record.
"""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Indicator, Organisation, Role
from tests.conftest import (
    auth_header,
    make_area,
    make_evidence,
    make_organisation,
    make_source,
    member,
)
from tests.test_projects import make_project


def make_indicator(db: Session, organisation: Organisation, **overrides) -> Indicator:
    """Create a persisted indicator."""
    fields = {
        "organisation_id": organisation.id,
        "name": f"Indicator {uuid.uuid4().hex[:8]}",
        "unit": "households",
        "baseline_value": Decimal("100"),
        "target_value": Decimal("500"),
    }
    fields.update(overrides)

    indicator = Indicator(**fields)
    db.add(indicator)
    db.commit()
    db.refresh(indicator)
    return indicator


def approve(client: TestClient, db: Session, organisation: Organisation, evidence_id) -> None:
    """Take a record through verification and approval by two people."""
    verifier = member(db, organisation, Role.VERIFIER)
    approver = member(db, organisation, Role.APPROVER)

    client.post(f"/api/v1/evidence/{evidence_id}/verify", headers=auth_header(verifier))
    client.post(f"/api/v1/evidence/{evidence_id}/approve", headers=auth_header(approver))


class TestIndicatorMeasurement:
    def test_approval_carries_the_measurement_onto_the_indicator(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        indicator = make_indicator(db, organisation)
        evidence = make_evidence(
            db,
            organisation,
            indicator_id=indicator.id,
            measured_value=Decimal("320"),
            evidence_date=date(2026, 6, 1),
        )

        approve(client, db, organisation, evidence.id)

        db.refresh(indicator)
        assert indicator.current_value == Decimal("320.0000")
        assert indicator.current_value_date == date(2026, 6, 1)

    def test_an_unapproved_measurement_does_not_move_the_indicator(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A figure on a dashboard must trace to something that cleared review."""
        indicator = make_indicator(db, organisation)
        make_evidence(
            db,
            organisation,
            indicator_id=indicator.id,
            measured_value=Decimal("999"),
            evidence_date=date(2026, 6, 1),
        )

        db.refresh(indicator)
        assert indicator.current_value is None

    def test_an_older_measurement_does_not_overwrite_a_newer_one(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Approving a backdated record later must not rewind the indicator."""
        indicator = make_indicator(db, organisation)

        recent = make_evidence(
            db,
            organisation,
            indicator_id=indicator.id,
            measured_value=Decimal("400"),
            evidence_date=date(2026, 6, 1),
        )
        approve(client, db, organisation, recent.id)

        older = make_evidence(
            db,
            organisation,
            indicator_id=indicator.id,
            measured_value=Decimal("150"),
            evidence_date=date(2026, 1, 1),
        )
        approve(client, db, organisation, older.id)

        db.refresh(indicator)
        assert indicator.current_value == Decimal("400.0000")
        assert indicator.current_value_date == date(2026, 6, 1)

    def test_evidence_without_a_measurement_leaves_the_indicator_alone(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        indicator = make_indicator(db, organisation)
        evidence = make_evidence(db, organisation, indicator_id=indicator.id)

        approve(client, db, organisation, evidence.id)

        db.refresh(indicator)
        assert indicator.current_value is None


class TestLinkedRecordIntegrity:
    def test_an_indicator_from_another_organisation_is_rejected(
        self,
        client: TestClient,
        db: Session,
        organisation: Organisation,
        other_organisation: Organisation,
    ):
        foreign = make_indicator(db, other_organisation)
        source = make_source(db, organisation)
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/evidence/",
            json={
                "title": "Cross tenant measurement",
                "organisation_id": str(organisation.id),
                "source_id": str(source.id),
                "indicator_id": str(foreign.id),
                "measured_value": "10",
            },
            headers=auth_header(author),
        )
        assert response.status_code == 400

    def test_a_project_from_another_organisation_is_rejected(
        self,
        client: TestClient,
        db: Session,
        organisation: Organisation,
        other_organisation: Organisation,
    ):
        foreign = make_project(db, other_organisation)
        source = make_source(db, organisation)
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/evidence/",
            json={
                "title": "Cross tenant project link",
                "organisation_id": str(organisation.id),
                "source_id": str(source.id),
                "project_id": str(foreign.id),
            },
            headers=auth_header(author),
        )
        assert response.status_code == 400

    def test_an_unknown_geographic_area_is_rejected(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/evidence/",
            json={
                "title": "Nowhere",
                "organisation_id": str(organisation.id),
                "source_id": str(source.id),
                "geography_id": str(uuid.uuid4()),
            },
            headers=auth_header(author),
        )
        assert response.status_code == 404

    def test_a_valid_area_is_accepted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        area = make_area(db)
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/evidence/",
            json={
                "title": "Placed evidence",
                "organisation_id": str(organisation.id),
                "source_id": str(source.id),
                "geography_id": str(area.id),
            },
            headers=auth_header(author),
        )
        assert response.status_code == 201
        assert response.json()["geography_id"] == str(area.id)


class TestPermanentReference:
    def test_the_reference_is_returned_on_creation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        source = make_source(db, organisation)
        author = member(db, organisation, Role.RESEARCHER)

        response = client.post(
            "/api/v1/evidence/",
            json={
                "title": "Citable record",
                "organisation_id": str(organisation.id),
                "source_id": str(source.id),
            },
            headers=auth_header(author),
        )
        assert response.status_code == 201
        assert response.json()["reference"].startswith("EV-")

    def test_references_are_unique_across_organisations(self, db: Session):
        first = make_evidence(db, make_organisation(db))
        second = make_evidence(db, make_organisation(db))

        assert first.reference != second.reference
