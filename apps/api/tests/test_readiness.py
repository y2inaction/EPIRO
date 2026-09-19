"""Readiness and scenarios (spec sections 28-31).

The rule this file exists to hold: **a readiness status may be declared as bad
as you like, and no better than the record supports.**

A readiness colour is the most quotable thing the platform produces and the one
with no evidence attached by construction. So the floor is computed from four
things the system knows — whether a plan exists, whether it has been
rehearsed, whether the rehearsal is current, and whether anything critical it
found is still open — and nobody, including a platform administrator, may
declare past it.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Drill,
    DrillStatus,
    FindingSeverity,
    Organisation,
    ReadinessStatus,
    Role,
    Scenario,
    User,
)
from app.services import readiness
from tests.conftest import auth_header, make_platform_admin, member

BASE = "/api/v1/scenarios"


@pytest.fixture
def manager(db: Session, organisation: Organisation) -> User:
    """Someone who may declare how ready the organisation is."""
    return member(db, organisation, Role.EXECUTIVE)


@pytest.fixture
def second_manager(db: Session, organisation: Organisation) -> User:
    return member(db, organisation, Role.ANALYST)


@pytest.fixture
def conductor(db: Session, organisation: Organisation) -> User:
    """Someone who runs rehearsals but does not declare readiness."""
    return member(db, organisation, Role.FIELD_OFFICER)


def create_scenario(
    client: TestClient, user: User, organisation: Organisation, **overrides: Any
) -> Dict[str, Any]:
    """Register a scenario."""
    payload: Dict[str, Any] = {
        "organisation_id": str(organisation.id),
        "name": f"Flood response {uuid.uuid4().hex[:6]}",
        "description": "What we do when the river rises.",
        "trigger": "River level above 6 metres at the Bida gauge.",
        "drill_interval_days": 180,
    }
    payload.update(overrides)

    response = client.post(f"{BASE}/", json=payload, headers=auth_header(user))
    assert response.status_code == 201, response.text
    return response.json()


def set_playbook(client: TestClient, user: User, scenario_id: str, steps: Optional[List] = None):
    """Give a scenario a plan."""
    body = steps or [
        {
            "position": 1,
            "title": "Confirm the gauge reading",
            "action": "Call the gauge station and confirm the level directly.",
            "responsible_role": Role.FIELD_OFFICER.value,
            "within_hours": 1,
        },
        {
            "position": 2,
            "title": "Notify the ward heads",
            "action": "Contact each ward head in the flood plain.",
            "responsible_role": Role.CONTENT_MANAGER.value,
            "within_hours": 2,
        },
    ]
    return client.put(
        f"{BASE}/{scenario_id}/playbook", json={"steps": body}, headers=auth_header(user)
    )


def run_drill(
    client: TestClient,
    manager: User,
    conductor: User,
    scenario_id: str,
    findings: Optional[List] = None,
) -> Dict[str, Any]:
    """Schedule and complete a rehearsal."""
    scheduled = client.post(
        f"{BASE}/{scenario_id}/drills",
        json={"scheduled_for": date.today().isoformat()},
        headers=auth_header(manager),
    )
    assert scheduled.status_code == 201, scheduled.text
    drill_id = scheduled.json()["id"]

    completed = client.post(
        f"{BASE}/drills/{drill_id}/complete",
        json={
            "summary": "Rehearsed the call-down. Two ward heads unreachable.",
            "findings": findings or [],
        },
        headers=auth_header(conductor),
    )
    assert completed.status_code == 200, completed.text
    return completed.json()


def declare(client: TestClient, user: User, scenario_id: str, status: ReadinessStatus):
    """Declare a readiness status with a rationale."""
    return client.post(
        f"{BASE}/{scenario_id}/declare",
        json={"status": status.value, "rationale": "Reviewed at the quarterly meeting."},
        headers=auth_header(user),
    )


# --- The floor -------------------------------------------------------------


class TestTheFloor:
    def test_a_new_scenario_starts_red_not_green(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        """A record with nothing behind it must not read as ready."""
        scenario = create_scenario(client, manager, organisation)

        assert scenario["status"] == ReadinessStatus.RED.value
        assert scenario["floor"]["status"] == ReadinessStatus.RED.value

    def test_no_playbook_holds_the_floor_at_red(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        floor = scenario["floor"]
        assert floor["status"] == ReadinessStatus.RED.value
        assert any("no playbook" in reason for reason in floor["reasons"])

    def test_a_plan_that_was_never_rehearsed_holds_the_floor_at_amber(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)
        response = set_playbook(client, manager, scenario["id"])

        assert response.status_code == 200, response.text
        floor = response.json()["floor"]
        assert floor["status"] == ReadinessStatus.AMBER.value
        assert any("never been rehearsed" in reason for reason in floor["reasons"])

    def test_a_rehearsed_current_plan_permits_green(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(client, manager, conductor, scenario["id"])

        floor = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()["floor"]

        assert floor["status"] == ReadinessStatus.GREEN.value
        assert floor["reasons"] == []

    def test_an_overdue_rehearsal_holds_the_floor_at_amber(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation, drill_interval_days=30)
        set_playbook(client, manager, scenario["id"])
        run_drill(client, manager, conductor, scenario["id"])

        # Age the completed drill past the interval.
        record = db.get(Scenario, uuid.UUID(scenario["id"]))
        drill = record.drills[0]
        drill.completed_at = datetime.now(timezone.utc) - timedelta(days=60)
        db.commit()

        floor = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()["floor"]

        assert floor["status"] == ReadinessStatus.AMBER.value
        assert any("beyond the 30-day interval" in reason for reason in floor["reasons"])

    def test_an_open_critical_finding_holds_the_floor_at_amber(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {
                    "description": "The ward head contact list is two years out of date.",
                    "severity": FindingSeverity.CRITICAL.value,
                }
            ],
        )

        floor = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()["floor"]

        assert floor["status"] == ReadinessStatus.AMBER.value
        # Asserted in full rather than by substring. A reason is read by the
        # person being told to fix something, and the first version of this
        # said "1 critical finding ... remain open" because the test only
        # looked for two words of it.
        assert "1 critical finding from a rehearsal remains open" in floor["reasons"]

    def test_several_open_critical_findings_read_as_plural(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {"description": "The contact list is stale.", "severity": "critical"},
                {"description": "The standby generator did not start.", "severity": "critical"},
            ],
        )

        floor = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()["floor"]

        assert "2 critical findings from a rehearsal remain open" in floor["reasons"]

    def test_a_non_critical_finding_does_not_hold_the_floor_down(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        """An observation is recorded without capping the colour."""
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {
                    "description": "The call script could be shorter.",
                    "severity": FindingSeverity.OBSERVATION.value,
                }
            ],
        )

        floor = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()["floor"]

        assert floor["status"] == ReadinessStatus.GREEN.value

    def test_a_cancelled_drill_does_not_count_as_a_rehearsal(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        """Otherwise scheduling and cancelling would launder a scenario green."""
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])

        scheduled = client.post(
            f"{BASE}/{scenario['id']}/drills",
            json={"scheduled_for": date.today().isoformat()},
            headers=auth_header(manager),
        )
        cancelled = client.post(
            f"{BASE}/drills/{scheduled.json()['id']}/cancel",
            json={"reason": "The venue was unavailable."},
            headers=auth_header(manager),
        )
        assert cancelled.status_code == 200, cancelled.text

        floor = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()["floor"]

        assert floor["status"] == ReadinessStatus.AMBER.value
        assert any("never been rehearsed" in reason for reason in floor["reasons"])


# --- Declaring -------------------------------------------------------------


class TestDeclaring:
    def test_declaring_better_than_the_record_supports_is_refused(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        response = declare(client, manager, scenario["id"], ReadinessStatus.GREEN)

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "cannot be declared green" in detail
        assert "no playbook" in detail

    def test_a_platform_administrator_is_not_exempt(
        self, client: TestClient, db: Session, manager: User, organisation: Organisation
    ):
        """A privilege that could switch the cap off would defeat it entirely."""
        scenario = create_scenario(client, manager, organisation)
        admin = make_platform_admin(db)

        response = declare(client, admin, scenario["id"], ReadinessStatus.GREEN)

        assert response.status_code == 409

    def test_declaring_worse_than_the_floor_is_allowed(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        """An owner may know something the database does not."""
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(client, manager, conductor, scenario["id"])

        response = client.post(
            f"{BASE}/{scenario['id']}/declare",
            json={
                "status": ReadinessStatus.BLACK.value,
                "rationale": "The only trained coordinator left the organisation last week.",
            },
            headers=auth_header(manager),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == ReadinessStatus.BLACK.value
        assert body["floor"]["status"] == ReadinessStatus.GREEN.value

    def test_declaring_green_works_once_the_record_supports_it(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(client, manager, conductor, scenario["id"])

        response = declare(client, manager, scenario["id"], ReadinessStatus.GREEN)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == ReadinessStatus.GREEN.value
        assert body["status_declared_by"] == str(manager.id)
        assert body["status_rationale"]

    def test_a_declaration_without_a_rationale_is_not_expressible(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        response = client.post(
            f"{BASE}/{scenario['id']}/declare",
            json={"status": ReadinessStatus.RED.value},
            headers=auth_header(manager),
        )

        assert response.status_code == 422

    def test_the_declaration_records_the_floor_it_was_measured_against(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(client, manager, conductor, scenario["id"])
        declare(client, manager, scenario["id"], ReadinessStatus.GREEN)

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == uuid.UUID(scenario["id"]),
                AuditLog.action == "declared",
            )
            .one()
        )
        assert entry.new_values["status"] == ReadinessStatus.GREEN.value
        assert entry.new_values["floor"] == ReadinessStatus.GREEN.value

    def test_a_conductor_cannot_declare_readiness(
        self, client: TestClient, conductor: User, manager: User, organisation: Organisation
    ):
        """Running a rehearsal and declaring a body ready are different acts."""
        scenario = create_scenario(client, manager, organisation)

        response = declare(client, conductor, scenario["id"], ReadinessStatus.RED)

        assert response.status_code == 403

    def test_completing_a_drill_does_not_silently_improve_the_status(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        """A machine must not raise a public-facing claim on somebody's behalf."""
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        run_drill(client, manager, conductor, scenario["id"])

        body = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()

        assert body["floor"]["status"] == ReadinessStatus.GREEN.value
        assert body["status"] == ReadinessStatus.RED.value


# --- Playbooks -------------------------------------------------------------


class TestPlaybooks:
    def test_a_step_must_name_who_acts(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        """A plan that does not say whose job something is, is not a plan."""
        scenario = create_scenario(client, manager, organisation)

        response = client.put(
            f"{BASE}/{scenario['id']}/playbook",
            json={
                "steps": [
                    {"position": 1, "title": "Do the thing", "action": "Somehow."},
                ]
            },
            headers=auth_header(manager),
        )

        assert response.status_code == 422

    def test_steps_must_be_numbered_without_gaps(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        response = set_playbook(
            client,
            manager,
            scenario["id"],
            steps=[
                {
                    "position": 1,
                    "title": "First",
                    "action": "Act.",
                    "responsible_role": Role.FIELD_OFFICER.value,
                },
                {
                    "position": 3,
                    "title": "Third",
                    "action": "Act.",
                    "responsible_role": Role.FIELD_OFFICER.value,
                },
            ],
        )

        assert response.status_code == 400
        assert "no gaps or repeats" in response.json()["detail"]

    def test_an_empty_playbook_is_refused(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        response = client.put(
            f"{BASE}/{scenario['id']}/playbook",
            json={"steps": []},
            headers=auth_header(manager),
        )

        assert response.status_code == 422

    def test_replacing_a_playbook_keeps_the_steps_ordered(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])

        response = set_playbook(
            client,
            manager,
            scenario["id"],
            steps=[
                {
                    "position": 2,
                    "title": "Second",
                    "action": "Act.",
                    "responsible_role": Role.EXECUTIVE.value,
                },
                {
                    "position": 1,
                    "title": "First",
                    "action": "Act.",
                    "responsible_role": Role.FIELD_OFFICER.value,
                },
            ],
        )

        assert response.status_code == 200, response.text
        steps = response.json()["playbook_steps"]
        assert [step["position"] for step in steps] == [1, 2]
        assert steps[0]["title"] == "First"


# --- Drills ----------------------------------------------------------------


class TestDrills:
    def test_a_completed_drill_requires_an_account_of_it(
        self, client: TestClient, manager: User, conductor: User, organisation: Organisation
    ):
        """A date is what the previous design mistook for readiness."""
        scenario = create_scenario(client, manager, organisation)
        scheduled = client.post(
            f"{BASE}/{scenario['id']}/drills",
            json={"scheduled_for": date.today().isoformat()},
            headers=auth_header(manager),
        )

        response = client.post(
            f"{BASE}/drills/{scheduled.json()['id']}/complete",
            json={"findings": []},
            headers=auth_header(conductor),
        )

        assert response.status_code == 422

    def test_a_drill_cannot_be_completed_twice(
        self, client: TestClient, manager: User, conductor: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)
        drill = run_drill(client, manager, conductor, scenario["id"])

        response = client.post(
            f"{BASE}/drills/{drill['id']}/complete",
            json={"summary": "Again."},
            headers=auth_header(conductor),
        )

        assert response.status_code == 409

    def test_a_cancelled_drill_stays_on_the_record_with_its_reason(
        self, client: TestClient, manager: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)
        scheduled = client.post(
            f"{BASE}/{scenario['id']}/drills",
            json={"scheduled_for": date.today().isoformat()},
            headers=auth_header(manager),
        )
        client.post(
            f"{BASE}/drills/{scheduled.json()['id']}/cancel",
            json={"reason": "The venue was unavailable."},
            headers=auth_header(manager),
        )

        drills = client.get(f"{BASE}/{scenario['id']}/drills", headers=auth_header(manager)).json()

        assert len(drills) == 1
        assert drills[0]["status"] == DrillStatus.CANCELLED.value
        assert drills[0]["cancellation_reason"] == "The venue was unavailable."

    def test_the_last_drill_date_comes_from_the_drill_record(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        """So the date and the account of what happened cannot disagree."""
        scenario = create_scenario(client, manager, organisation)
        run_drill(client, manager, conductor, scenario["id"])

        record = db.get(Scenario, uuid.UUID(scenario["id"]))
        db.refresh(record)
        assert record.last_drill_date == date.today()

    def test_completing_a_drill_is_recorded_in_the_audit_trail(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        drill = run_drill(client, manager, conductor, scenario["id"])

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == uuid.UUID(drill["id"]),
                AuditLog.action == "completed",
            )
            .one()
        )
        assert entry.user_id == conductor.id


# --- Findings --------------------------------------------------------------


class TestFindings:
    def test_the_person_who_raised_a_finding_may_not_confirm_it_resolved(
        self,
        client: TestClient,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        """Self-certification is what the cap on readiness exists to prevent."""
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        drill = run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {
                    "description": "The contact list is out of date.",
                    "severity": FindingSeverity.CRITICAL.value,
                }
            ],
        )
        finding_id = drill["findings"][0]["id"]

        response = client.post(
            f"{BASE}/findings/{finding_id}/resolve",
            json={"resolution": "I updated it."},
            headers=auth_header(conductor),
        )

        assert response.status_code == 403
        assert "Separation of duties" in response.json()["detail"]

    def test_someone_else_can_confirm_it_resolved(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        drill = run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {
                    "description": "The contact list is out of date.",
                    "severity": FindingSeverity.CRITICAL.value,
                }
            ],
        )
        other = member(db, organisation, Role.EVIDENCE_MANAGER)

        response = client.post(
            f"{BASE}/findings/{drill['findings'][0]['id']}/resolve",
            json={"resolution": "Checked against the ward register and rebuilt."},
            headers=auth_header(other),
        )

        assert response.status_code == 200, response.text
        assert response.json()["resolved_by"] == str(other.id)

    def test_resolving_a_critical_finding_lifts_the_floor(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        set_playbook(client, manager, scenario["id"])
        drill = run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {
                    "description": "The contact list is out of date.",
                    "severity": FindingSeverity.CRITICAL.value,
                }
            ],
        )
        other = member(db, organisation, Role.EVIDENCE_MANAGER)

        before = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()
        assert before["floor"]["status"] == ReadinessStatus.AMBER.value

        client.post(
            f"{BASE}/findings/{drill['findings'][0]['id']}/resolve",
            json={"resolution": "Rebuilt from the ward register."},
            headers=auth_header(other),
        )

        after = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(manager)).json()
        assert after["floor"]["status"] == ReadinessStatus.GREEN.value

    def test_a_finding_cannot_be_resolved_twice(
        self,
        client: TestClient,
        db: Session,
        manager: User,
        conductor: User,
        organisation: Organisation,
    ):
        scenario = create_scenario(client, manager, organisation)
        drill = run_drill(
            client,
            manager,
            conductor,
            scenario["id"],
            findings=[
                {"description": "A gap.", "severity": FindingSeverity.MAJOR.value},
            ],
        )
        other = member(db, organisation, Role.EVIDENCE_MANAGER)
        finding_id = drill["findings"][0]["id"]

        client.post(
            f"{BASE}/findings/{finding_id}/resolve",
            json={"resolution": "Closed."},
            headers=auth_header(other),
        )
        again = client.post(
            f"{BASE}/findings/{finding_id}/resolve",
            json={"resolution": "Closed again."},
            headers=auth_header(other),
        )

        assert again.status_code == 409

    def test_a_finding_describes_the_response_not_a_person(self):
        """Spec section 4, asserted against the schema itself.

        A drill is the obvious place a blame column would appear. There is
        none, and this fails if one is added.
        """
        from app.models import DrillFinding

        columns = set(DrillFinding.__table__.columns.keys())
        forbidden = {
            "at_fault",
            "blamed_user_id",
            "responsible_person",
            "performance_score",
            "failed_by",
        }
        assert columns & forbidden == set()


# --- Tenancy ---------------------------------------------------------------


class TestTenancy:
    def test_another_body_cannot_read_a_scenario(
        self, client: TestClient, manager: User, outsider: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        response = client.get(f"{BASE}/{scenario['id']}", headers=auth_header(outsider))

        assert response.status_code == 404

    def test_another_body_cannot_declare_readiness_for_it(
        self, client: TestClient, manager: User, outsider: User, organisation: Organisation
    ):
        scenario = create_scenario(client, manager, organisation)

        response = declare(client, outsider, scenario["id"], ReadinessStatus.BLACK)

        assert response.status_code == 404

    def test_the_matrix_lists_only_the_caller_s_organisations(
        self, client: TestClient, manager: User, outsider: User, organisation: Organisation
    ):
        create_scenario(client, manager, organisation)

        response = client.get(f"{BASE}/", headers=auth_header(outsider))

        assert response.status_code == 200
        assert response.json()["total"] == 0


# --- The floor computed directly -------------------------------------------


class TestFloorUnit:
    """The ordering the whole rule rests on, checked without HTTP."""

    def test_severity_ordering_is_worst_last(self):
        floor = readiness.Floor(status=ReadinessStatus.AMBER, reasons=[])

        assert floor.permits(ReadinessStatus.AMBER)
        assert floor.permits(ReadinessStatus.RED)
        assert floor.permits(ReadinessStatus.BLACK)
        assert not floor.permits(ReadinessStatus.GREEN)

    def test_a_scenario_with_no_cadence_falls_back_to_a_year(
        self, db: Session, organisation: Organisation
    ):
        scenario = Scenario(organisation_id=organisation.id, name="No cadence")
        db.add(scenario)
        db.commit()

        completed_at = datetime.now(timezone.utc) - timedelta(days=200)
        drill = Drill(
            scenario_id=scenario.id,
            scheduled_for=date.today(),
            status=DrillStatus.COMPLETED,
            completed_at=completed_at,
        )
        db.add(drill)
        db.commit()
        db.refresh(scenario)

        assert readiness.last_completion(scenario.drills) == completed_at
        assert readiness.drill_is_current(scenario, completed_at, date.today())
