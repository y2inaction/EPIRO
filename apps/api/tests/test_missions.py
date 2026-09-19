"""Field operations and missions (spec section 18).

Four things these tests hold.

* **No approval without a written risk assessment.** Sending people somewhere
  is the one action the platform authorises whose cost falls on staff rather
  than on a record.
* **The planner may not approve their own mission.** Somebody else has to have
  read the risk assessment.
* **A field capture is idempotent on its capture key.** A device on a bad
  connection retries, and a capture endpoint that duplicated on retry could
  not be built on later.
* **There is nowhere to accumulate a movement trail.** A check-in is a state,
  not a position, and the schema has no column for one — asserted directly,
  because a later contributor adding "just a lat/long for safety" is exactly
  how this would be lost.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Evidence,
    EvidenceStatus,
    FieldMission,
    MissionCheckIn,
    MissionMember,
    MissionStatus,
    Organisation,
    Role,
    SafetyState,
    User,
)
from app.services import missions
from tests.conftest import auth_header, make_source, member

BASE = "/api/v1/missions"

RISK = (
    "The road past the bridge floods after rain. The team travels in one vehicle, "
    "carries a satellite phone, and turns back if the water is over the axle."
)


@pytest.fixture
def coordinator(db: Session, organisation: Organisation) -> User:
    """Someone who plans and authorises missions."""
    return member(db, organisation, Role.EVIDENCE_MANAGER)


@pytest.fixture
def approver(db: Session, organisation: Organisation) -> User:
    """A second coordinator, so the planner need not approve their own trip."""
    return member(db, organisation, Role.EXECUTIVE)


@pytest.fixture
def officer(db: Session, organisation: Organisation) -> User:
    """Someone who goes on the mission."""
    return member(db, organisation, Role.FIELD_OFFICER)


def plan(
    client: TestClient, user: User, organisation: Organisation, **overrides: Any
) -> Dict[str, Any]:
    """Plan a mission."""
    payload: Dict[str, Any] = {
        "organisation_id": str(organisation.id),
        "title": f"Borehole verification {uuid.uuid4().hex[:6]}",
        "purpose": "Confirm the boreholes recorded as completed in August exist and run.",
        "planned_start": date.today().isoformat(),
        "planned_end": (date.today() + timedelta(days=3)).isoformat(),
        "check_in_interval_hours": 12,
    }
    payload.update(overrides)

    response = client.post(f"{BASE}/", json=payload, headers=auth_header(user))
    assert response.status_code == 201, response.text
    return response.json()


def take_to_running(
    client: TestClient,
    coordinator: User,
    approver: User,
    officer: User,
    organisation: Organisation,
) -> Dict[str, Any]:
    """Plan, approve and start a mission."""
    mission = plan(client, coordinator, organisation, risk_assessment=RISK)

    approved = client.post(f"{BASE}/{mission['id']}/approve", headers=auth_header(approver))
    assert approved.status_code == 200, approved.text

    started = client.post(f"{BASE}/{mission['id']}/start", headers=auth_header(officer))
    assert started.status_code == 200, started.text
    return started.json()


def capture(
    client: TestClient,
    user: User,
    mission_id: str,
    source_id: uuid.UUID,
    key: Optional[str] = None,
    **overrides: Any,
):
    """File an observation against a mission."""
    body: Dict[str, Any] = {
        "capture_key": key or f"cap-{uuid.uuid4().hex}",
        "title": "Borehole 4 at Lemu — running",
        "description": "Pump running, handle intact, queue of about twenty people.",
        "source_id": str(source_id),
    }
    body.update(overrides)
    return client.post(f"{BASE}/{mission_id}/evidence", json=body, headers=auth_header(user))


# --- Planning and approval -------------------------------------------------


class TestPlanning:
    def test_a_mission_is_planned_with_its_team(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = plan(
            client,
            coordinator,
            organisation,
            members=[{"user_id": str(officer.id), "role_on_mission": "Lead enumerator"}],
        )

        assert mission["status"] == MissionStatus.PLANNED.value
        assert len(mission["members"]) == 1
        assert mission["members"][0]["user_id"] == str(officer.id)

    def test_a_mission_cannot_end_before_it_starts(
        self, client: TestClient, coordinator: User, organisation: Organisation
    ):
        response = client.post(
            f"{BASE}/",
            json={
                "organisation_id": str(organisation.id),
                "title": "Backwards",
                "purpose": "Impossible.",
                "planned_start": date.today().isoformat(),
                "planned_end": (date.today() - timedelta(days=1)).isoformat(),
            },
            headers=auth_header(coordinator),
        )

        assert response.status_code == 400
        assert "cannot end before it starts" in response.json()["detail"]

    def test_a_field_officer_cannot_authorise_their_own_trip(
        self, client: TestClient, officer: User, organisation: Organisation
    ):
        """Planning a mission is a coordination act with a duty of care."""
        response = client.post(
            f"{BASE}/",
            json={
                "organisation_id": str(organisation.id),
                "title": "Self-authorised",
                "purpose": "Going anyway.",
                "planned_start": date.today().isoformat(),
                "planned_end": date.today().isoformat(),
            },
            headers=auth_header(officer),
        )

        assert response.status_code == 403

    def test_an_unknown_team_member_is_refused(
        self, client: TestClient, coordinator: User, organisation: Organisation
    ):
        response = client.post(
            f"{BASE}/",
            json={
                "organisation_id": str(organisation.id),
                "title": "Phantom team",
                "purpose": "Checking.",
                "planned_start": date.today().isoformat(),
                "planned_end": date.today().isoformat(),
                "members": [{"user_id": str(uuid.uuid4())}],
            },
            headers=auth_header(coordinator),
        )

        assert response.status_code == 400


class TestApproval:
    def test_a_mission_cannot_be_approved_without_a_risk_assessment(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        organisation: Organisation,
    ):
        """The rule whose cost falls on people rather than on data."""
        mission = plan(client, coordinator, organisation)

        response = client.post(f"{BASE}/{mission['id']}/approve", headers=auth_header(approver))

        assert response.status_code == 400
        assert "without a written risk assessment" in response.json()["detail"]

    def test_a_whitespace_risk_assessment_does_not_count(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        organisation: Organisation,
    ):
        mission = plan(client, coordinator, organisation, risk_assessment="   ")

        response = client.post(f"{BASE}/{mission['id']}/approve", headers=auth_header(approver))

        assert response.status_code == 400

    def test_the_planner_may_not_approve_their_own_mission(
        self, client: TestClient, coordinator: User, organisation: Organisation
    ):
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)

        response = client.post(f"{BASE}/{mission['id']}/approve", headers=auth_header(coordinator))

        assert response.status_code == 403
        assert "Separation of duties" in response.json()["detail"]

    def test_someone_else_approves_it(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        organisation: Organisation,
    ):
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)

        response = client.post(f"{BASE}/{mission['id']}/approve", headers=auth_header(approver))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == MissionStatus.APPROVED.value
        assert body["approved_by"] == str(approver.id)

    def test_an_unapproved_mission_cannot_start(
        self,
        client: TestClient,
        coordinator: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)

        response = client.post(f"{BASE}/{mission['id']}/start", headers=auth_header(officer))

        assert response.status_code == 409

    def test_an_approved_mission_cannot_be_quietly_edited(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        organisation: Organisation,
    ):
        """What was approved is what somebody signed off on."""
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)
        client.post(f"{BASE}/{mission['id']}/approve", headers=auth_header(approver))

        response = client.put(
            f"{BASE}/{mission['id']}",
            json={"risk_assessment": "Actually it is completely safe."},
            headers=auth_header(coordinator),
        )

        assert response.status_code == 409


# --- Safety ----------------------------------------------------------------


class TestSafety:
    def test_a_check_in_records_a_state(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        response = client.post(
            f"{BASE}/{mission['id']}/check-in",
            json={"state": SafetyState.SAFE.value, "note": "At Lemu, all well."},
            headers=auth_header(officer),
        )

        assert response.status_code == 201, response.text
        assert response.json()["state"] == SafetyState.SAFE.value

    def test_a_check_in_has_nowhere_to_put_a_position(self):
        """Spec section 20, asserted against the schema itself.

        A coordinator needs to know whether a team is safe. A stream of
        coordinates would additionally build a continuous record of where
        individual staff went, which the operational purpose does not require.
        Adding "just a lat/long for safety" is how that would be lost, so this
        test fails if anyone does.
        """
        columns = set(MissionCheckIn.__table__.columns.keys())
        forbidden = {
            "latitude",
            "longitude",
            "location",
            "coordinates",
            "position",
            "geom",
            "accuracy",
            "heading",
            "speed",
        }
        assert columns & forbidden == set()

    def test_a_mission_member_carries_no_position_either(self):
        """The same rule, on the table that names the individuals."""
        columns = set(MissionMember.__table__.columns.keys())
        forbidden = {"latitude", "longitude", "location", "last_seen_at", "device_id"}
        assert columns & forbidden == set()

    def test_a_mission_has_no_column_for_the_citizens_it_spoke_to(self):
        """Where an account becomes evidence it goes through the source registry."""
        columns = set(FieldMission.__table__.columns.keys())
        forbidden = {
            "people_contacted",
            "interviewees",
            "respondents",
            "citizen_ids",
            "household_list",
        }
        assert columns & forbidden == set()

    def test_a_running_mission_that_has_not_reported_becomes_overdue(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        record = db.get(FieldMission, uuid.UUID(mission["id"]))
        record.started_at = datetime.now(timezone.utc) - timedelta(hours=30)
        db.commit()

        body = client.get(f"{BASE}/{mission['id']}", headers=auth_header(coordinator)).json()

        assert body["safety"]["overdue"] is True
        assert body["safety"]["needs_attention"] is True

    def test_a_recent_check_in_clears_the_overdue_state(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        record = db.get(FieldMission, uuid.UUID(mission["id"]))
        record.started_at = datetime.now(timezone.utc) - timedelta(hours=30)
        db.commit()

        client.post(
            f"{BASE}/{mission['id']}/check-in",
            json={"state": SafetyState.SAFE.value},
            headers=auth_header(officer),
        )

        body = client.get(f"{BASE}/{mission['id']}", headers=auth_header(coordinator)).json()
        assert body["safety"]["overdue"] is False

    def test_asking_for_help_needs_attention_even_when_not_overdue(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        client.post(
            f"{BASE}/{mission['id']}/check-in",
            json={
                "state": SafetyState.ASSISTANCE_REQUIRED.value,
                "note": "Vehicle stuck past the bridge.",
            },
            headers=auth_header(officer),
        )

        body = client.get(f"{BASE}/{mission['id']}", headers=auth_header(coordinator)).json()
        assert body["safety"]["overdue"] is False
        assert body["safety"]["needs_attention"] is True
        assert body["safety"]["state"] == SafetyState.ASSISTANCE_REQUIRED.value

    def test_a_mission_not_under_way_is_never_overdue(
        self, client: TestClient, coordinator: User, organisation: Organisation
    ):
        """A team that has not left is not missing."""
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)

        body = client.get(f"{BASE}/{mission['id']}", headers=auth_header(coordinator)).json()

        assert body["safety"]["overdue"] is False
        assert body["safety"]["needs_attention"] is False

    def test_the_attention_list_shows_only_missions_that_need_it(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        quiet = take_to_running(client, coordinator, approver, officer, organisation)
        client.post(
            f"{BASE}/{quiet['id']}/check-in",
            json={"state": SafetyState.SAFE.value},
            headers=auth_header(officer),
        )

        stuck = take_to_running(client, coordinator, approver, officer, organisation)
        client.post(
            f"{BASE}/{stuck['id']}/check-in",
            json={"state": SafetyState.ASSISTANCE_REQUIRED.value},
            headers=auth_header(officer),
        )

        listed = client.get(
            f"{BASE}/", params={"needs_attention": True}, headers=auth_header(coordinator)
        ).json()

        assert listed["total"] == 1
        assert listed["data"][0]["id"] == stuck["id"]

    def test_a_mission_not_under_way_cannot_be_checked_in_on(
        self,
        client: TestClient,
        coordinator: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)

        response = client.post(
            f"{BASE}/{mission['id']}/check-in",
            json={"state": SafetyState.SAFE.value},
            headers=auth_header(officer),
        )

        assert response.status_code == 409


# --- Capture ---------------------------------------------------------------


class TestCapture:
    def test_evidence_captured_on_a_mission_is_linked_to_it(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)

        response = capture(client, officer, mission["id"], source.id)

        assert response.status_code == 201, response.text
        record = db.get(Evidence, uuid.UUID(response.json()["id"]))
        assert record.field_mission_id == uuid.UUID(mission["id"])

    def test_a_field_capture_starts_as_an_unverified_draft(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """Going and looking is how evidence is gathered, not a way round review."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)

        response = capture(client, officer, mission["id"], source.id)

        body = response.json()
        assert body["status"] == EvidenceStatus.DRAFT.value
        assert body["verification_status"] == "unverified"

    def test_a_retried_capture_returns_the_same_record(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """The whole point: a device on a bad connection retries."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)
        key = f"cap-{uuid.uuid4().hex}"

        first = capture(client, officer, mission["id"], source.id, key=key)
        second = capture(client, officer, mission["id"], source.id, key=key)

        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

        filed = client.get(f"{BASE}/{mission['id']}/evidence", headers=auth_header(officer)).json()
        assert len(filed) == 1

    def test_a_retry_does_not_overwrite_what_was_filed(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """A retry is the same request arriving twice, not a revision."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)
        key = f"cap-{uuid.uuid4().hex}"

        first = capture(client, officer, mission["id"], source.id, key=key)
        second = capture(
            client, officer, mission["id"], source.id, key=key, title="Different title"
        )

        assert second.json()["title"] == first.json()["title"]

    def test_a_capture_that_loses_the_insert_race_returns_the_winner(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """Two retries arriving at once both look, both find nothing, both insert.

        The partial unique index settles it. Without the IntegrityError branch
        the loser would get a 500, and the promise that a retry is safe would
        hold only when the retries were far enough apart — which is exactly
        not the case on the connection that caused the retry.

        Simulated rather than raced, because a race that reproduces only
        sometimes is not a test. The row is inserted behind the request's back
        after it has already decided there is none.
        """
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)
        key = f"cap-{uuid.uuid4().hex}"

        from app.api import missions as missions_api

        original = missions_api.Evidence
        planted: Dict[str, Any] = {}

        class PlantsAConflict(original):  # type: ignore[misc, valid-type]
            """Inserts the competing row the instant this one is constructed."""

            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                if not planted:
                    winner = original(
                        organisation_id=organisation.id,
                        source_id=source.id,
                        title="Filed by the other retry",
                        capture_key=key,
                        field_mission_id=uuid.UUID(mission["id"]),
                    )
                    db.add(winner)
                    db.commit()
                    planted["id"] = str(winner.id)

        missions_api.Evidence = PlantsAConflict
        try:
            response = capture(client, officer, mission["id"], source.id, key=key)
        finally:
            missions_api.Evidence = original

        assert response.status_code == 200, response.text
        assert response.json()["id"] == planted["id"]
        assert response.json()["title"] == "Filed by the other retry"

    def test_the_unique_index_is_scoped_per_organisation(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """Two bodies can use the same key without colliding."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)
        key = f"cap-{uuid.uuid4().hex}"

        assert capture(client, officer, mission["id"], source.id, key=key).status_code == 201

        # A second organisation's record with the same key inserts cleanly.
        from tests.conftest import make_evidence, make_organisation

        other = make_organisation(db)
        record = make_evidence(db, other, capture_key=key)
        assert record.capture_key == key

    def test_evidence_cannot_be_captured_against_a_mission_that_has_not_happened(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        officer: User,
        organisation: Organisation,
    ):
        """Filing against a trip nobody has taken makes the provenance false."""
        mission = plan(client, coordinator, organisation, risk_assessment=RISK)
        source = make_source(db, organisation)

        response = capture(client, officer, mission["id"], source.id)

        assert response.status_code == 409

    def test_a_capture_is_recorded_in_the_audit_trail(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        source = make_source(db, organisation)
        response = capture(client, officer, mission["id"], source.id)

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == uuid.UUID(response.json()["id"]),
                AuditLog.action == "captured",
            )
            .one()
        )
        assert entry.user_id == officer.id


# --- Completion ------------------------------------------------------------


class TestCompletion:
    def test_completing_requires_a_report(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        response = client.post(
            f"{BASE}/{mission['id']}/complete", json={}, headers=auth_header(officer)
        )

        assert response.status_code == 422

    def test_a_completed_mission_carries_its_report(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        response = client.post(
            f"{BASE}/{mission['id']}/complete",
            json={"report": "Four of the five boreholes were running. The fifth has no handle."},
            headers=auth_header(officer),
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == MissionStatus.COMPLETED.value
        assert "no handle" in response.json()["report"]

    def test_a_mission_under_way_can_be_recalled_with_a_reason(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """The case where a stated reason matters most."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        response = client.post(
            f"{BASE}/{mission['id']}/cancel",
            json={"reason": "Security advice changed; the team was recalled."},
            headers=auth_header(coordinator),
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == MissionStatus.CANCELLED.value
        assert response.json()["cancellation_reason"]

    def test_a_completed_mission_cannot_be_cancelled(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        client.post(
            f"{BASE}/{mission['id']}/complete",
            json={"report": "Done."},
            headers=auth_header(officer),
        )

        response = client.post(
            f"{BASE}/{mission['id']}/cancel",
            json={"reason": "Changed my mind."},
            headers=auth_header(coordinator),
        )

        assert response.status_code == 409

    def test_evidence_can_still_be_filed_after_completion(
        self,
        client: TestClient,
        db: Session,
        coordinator: User,
        approver: User,
        officer: User,
        organisation: Organisation,
    ):
        """A team writes up what it saw after it gets back."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)
        client.post(
            f"{BASE}/{mission['id']}/complete",
            json={"report": "Done."},
            headers=auth_header(officer),
        )
        source = make_source(db, organisation)

        assert capture(client, officer, mission["id"], source.id).status_code == 201


# --- Tenancy ---------------------------------------------------------------


class TestTenancy:
    def test_another_body_cannot_read_a_mission(
        self,
        client: TestClient,
        coordinator: User,
        outsider: User,
        organisation: Organisation,
    ):
        mission = plan(client, coordinator, organisation)

        response = client.get(f"{BASE}/{mission['id']}", headers=auth_header(outsider))

        assert response.status_code == 404

    def test_another_body_cannot_see_where_a_team_is(
        self,
        client: TestClient,
        coordinator: User,
        approver: User,
        officer: User,
        outsider: User,
        organisation: Organisation,
    ):
        """Mission records say where named staff are. Scoping them matters."""
        mission = take_to_running(client, coordinator, approver, officer, organisation)

        listed = client.get(f"{BASE}/", headers=auth_header(outsider)).json()
        check_ins = client.get(f"{BASE}/{mission['id']}/check-ins", headers=auth_header(outsider))

        assert listed["total"] == 0
        assert check_ins.status_code == 404


# --- The posture computed directly -----------------------------------------


class TestPostureUnit:
    def test_a_mission_with_no_interval_falls_back_to_a_day(
        self, db: Session, organisation: Organisation
    ):
        mission = FieldMission(
            organisation_id=organisation.id,
            title="No cadence",
            purpose="Checking.",
            planned_start=date.today(),
            planned_end=date.today(),
            status=MissionStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc) - timedelta(hours=20),
        )
        db.add(mission)
        db.commit()
        db.refresh(mission)

        assert missions.safety_posture(mission).overdue is False

        mission.started_at = datetime.now(timezone.utc) - timedelta(hours=26)
        db.commit()
        assert missions.safety_posture(mission).overdue is True

    def test_the_latest_check_in_is_the_one_that_counts(
        self, db: Session, organisation: Organisation, officer: User
    ):
        mission = FieldMission(
            organisation_id=organisation.id,
            title="Ordering",
            purpose="Checking.",
            planned_start=date.today(),
            planned_end=date.today(),
            status=MissionStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc) - timedelta(hours=5),
            check_in_interval_hours=12,
        )
        db.add(mission)
        db.commit()

        older = MissionCheckIn(
            mission_id=mission.id,
            state=SafetyState.ASSISTANCE_REQUIRED,
            reported_at=datetime.now(timezone.utc) - timedelta(hours=4),
        )
        newer = MissionCheckIn(
            mission_id=mission.id,
            state=SafetyState.SAFE,
            reported_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add_all([older, newer])
        db.commit()
        db.refresh(mission)

        posture = missions.safety_posture(mission)
        assert posture.state is SafetyState.SAFE
        assert posture.needs_attention is False
