"""The decision register (Phase 4: connecting intelligence to decisions).

The chain the specification draws ends here: evidence becomes a signal, a
signal is assessed into a finding, and the finding becomes an action somebody
owns and is answerable for. These tests hold the three rules that decide
whether the register is accountability or decoration.

**An action cites what prompted it**, and the citation is checked.
**Closing requires a written outcome**, because the status is not the
interesting part.
**Deciding not to act is recorded rather than deleted**, because the reason
for not acting is usually the part worth having.
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    Action,
    ActionStatus,
    IntegritySignal,
    Organisation,
    Role,
    User,
)
from app.services import actions as rules
from tests.conftest import auth_header, make_evidence, make_organisation, member

BASE = "/api/v1/actions"


@pytest.fixture
def owner(db: Session, organisation: Organisation) -> User:
    """Somebody who may raise and run actions."""
    return member(db, organisation, Role.EXECUTIVE)


def signal(db: Session, organisation: Organisation) -> IntegritySignal:
    """A claim already logged, which an action can be raised against."""
    record = IntegritySignal(
        organisation_id=organisation.id,
        claim=f"A claim circulating about {uuid.uuid4().hex[:6]}.",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def raise_action(
    client: TestClient, user: User, organisation: Organisation, origin: IntegritySignal, **extra
):
    body = {
        "organisation_id": str(organisation.id),
        "title": "Publish a correction in Hausa",
        "rationale": (
            "The claim is circulating on voice notes, which the English "
            "correction does not reach."
        ),
        "origin_type": "integrity_signal",
        "origin_id": str(origin.id),
        "owner_id": str(user.id),
    }
    body.update(extra)
    return client.post(f"{BASE}/", json=body, headers=auth_header(user))


class TestAnActionMustCiteWhatPromptedIt:
    def test_an_action_is_raised_against_a_signal(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        response = raise_action(client, owner, organisation, signal(db, organisation))

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "proposed"
        assert body["origin_type"] == "integrity_signal"
        assert body["owner_id"] == str(owner.id)

    def test_an_origin_that_does_not_exist_is_refused(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """A citation that points at nothing makes the citation decorative."""
        response = client.post(
            f"{BASE}/",
            json={
                "organisation_id": str(organisation.id),
                "title": "Do something",
                "rationale": "Because.",
                "origin_type": "integrity_signal",
                "origin_id": str(uuid.uuid4()),
                "owner_id": str(owner.id),
            },
            headers=auth_header(owner),
        )

        assert response.status_code == 400
        assert "cite something that exists" in response.json()["detail"]

    def test_an_origin_in_another_organisation_is_refused(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """Otherwise the register confirms which identifiers are real elsewhere."""
        theirs = signal(db, make_organisation(db))

        response = raise_action(client, owner, organisation, theirs)

        assert response.status_code == 400

    def test_the_chain_can_be_read_back_from_the_finding(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """A finding with no action against it is a thing nobody acted on."""
        claim = signal(db, organisation)
        raise_action(client, owner, organisation, claim)

        response = client.get(
            f"{BASE}/origin/integrity_signal/{claim.id}", headers=auth_header(owner)
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_an_action_can_rest_on_evidence_directly(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        record = make_evidence(db, organisation)

        response = client.post(
            f"{BASE}/",
            json={
                "organisation_id": str(organisation.id),
                "title": "Repeat the survey",
                "rationale": "The handover record does not match the ward register.",
                "origin_type": "evidence",
                "origin_id": str(record.id),
                "owner_id": str(owner.id),
            },
            headers=auth_header(owner),
        )

        assert response.status_code == 201


class TestClosingRequiresAnOutcome:
    def test_completing_without_saying_what_happened_is_refused(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]
        client.post(f"{BASE}/{action_id}/accept", headers=auth_header(owner))
        client.post(f"{BASE}/{action_id}/start", headers=auth_header(owner))

        response = client.post(
            f"{BASE}/{action_id}/complete", json={"outcome": "   "}, headers=auth_header(owner)
        )

        # Whitespace passes the length check and is still not an account of
        # what happened, which is why the rule lives in the service and not
        # only in the schema.
        assert response.status_code == 400
        assert "Write what happened" in response.json()["detail"]

    def test_a_completed_action_keeps_what_happened(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]
        client.post(f"{BASE}/{action_id}/accept", headers=auth_header(owner))
        client.post(f"{BASE}/{action_id}/start", headers=auth_header(owner))

        response = client.post(
            f"{BASE}/{action_id}/complete",
            json={"outcome": "Correction published in Hausa on 14 September."},
            headers=auth_header(owner),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "done"
        assert "Hausa" in body["outcome"]
        assert body["closed_at"] is not None

    def test_deciding_not_to_act_is_recorded_rather_than_deleted(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """The reason for not acting is usually the part worth having."""
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]

        response = client.post(
            f"{BASE}/{action_id}/drop",
            json={"outcome": "The claim stopped circulating before a correction was needed."},
            headers=auth_header(owner),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "dropped"
        assert db.query(Action).filter(Action.id == uuid.UUID(action_id)).first() is not None


class TestTheLifecycle:
    def test_an_action_cannot_skip_straight_to_done(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]

        response = client.post(
            f"{BASE}/{action_id}/complete",
            json={"outcome": "Done somehow."},
            headers=auth_header(owner),
        )

        assert response.status_code == 409
        assert "cannot go straight to done" in response.json()["detail"]

    def test_a_closed_action_is_not_reopened(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """A decision revisited is a new decision, with its own reasoning."""
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]
        client.post(
            f"{BASE}/{action_id}/drop",
            json={"outcome": "Not needed."},
            headers=auth_header(owner),
        )

        response = client.post(f"{BASE}/{action_id}/accept", headers=auth_header(owner))

        assert response.status_code == 409
        assert "Raise a new action" in response.json()["detail"]

    def test_a_closed_action_cannot_be_revised(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]
        client.post(
            f"{BASE}/{action_id}/drop", json={"outcome": "Not needed."}, headers=auth_header(owner)
        )

        response = client.patch(
            f"{BASE}/{action_id}", json={"title": "Something else"}, headers=auth_header(owner)
        )

        assert response.status_code == 409


class TestOverdue:
    def test_overdue_is_derived_from_the_date_and_the_state(self, db: Session):
        """Never stored: a stored flag is wrong the moment the clock passes it."""
        yesterday = date.today() - timedelta(days=1)

        waiting = Action(status=ActionStatus.ACCEPTED, due_date=yesterday)
        closed = Action(status=ActionStatus.DONE, due_date=yesterday)
        undated = Action(status=ActionStatus.ACCEPTED, due_date=None)

        assert rules.is_overdue(waiting) is True
        # A finished action is not chased past its date.
        assert rules.is_overdue(closed) is False
        assert rules.is_overdue(undated) is False

    def test_there_is_no_overdue_column_to_fall_out_of_date(self):
        assert "overdue" not in Action.__table__.columns.keys()

    def test_the_register_can_be_narrowed_to_what_is_late(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        late = raise_action(
            client,
            owner,
            organisation,
            signal(db, organisation),
            due_date=str(date.today() - timedelta(days=3)),
        ).json()
        raise_action(client, owner, organisation, signal(db, organisation))

        response = client.get(
            f"{BASE}/", params={"overdue": "true"}, headers=auth_header(owner)
        ).json()

        assert [row["id"] for row in response["data"]] == [late["id"]]


class TestTheRegisterIsAboutDecisionsNotPeople:
    def test_there_is_no_way_to_narrow_the_register_by_owner(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """Who owns an action is accountability. Slicing by person is a report on staff.

        Spec section 4's prohibition on profiling is not only about citizens.
        """
        raise_action(client, owner, organisation, signal(db, organisation))

        # An owner parameter is not accepted: it is ignored as unknown rather
        # than narrowing anything.
        response = client.get(
            f"{BASE}/", params={"owner_id": str(uuid.uuid4())}, headers=auth_header(owner)
        ).json()

        assert response["total"] == 1

    def test_no_action_dimension_groups_by_a_person(self):
        from app.services import intelligence

        measure = intelligence.MEASURES["actions"]

        for name in measure.dimensions:
            assert not name.endswith("_by")
            assert name not in {"owner_id", "created_by_id", "assigned_to"}

    def test_no_computed_priority_exists(self):
        """Ranking what matters is a judgement, not arithmetic.

        A generated score would launder that judgement into a number nobody
        can argue with.
        """
        columns = set(Action.__table__.columns.keys())

        assert not columns & {"priority_score", "score", "urgency", "risk_score", "weight"}


class TestTenancy:
    def test_an_action_in_another_organisation_is_not_visible(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        theirs = make_organisation(db)
        stranger = member(db, theirs, Role.EXECUTIVE)
        other_action = raise_action(client, stranger, theirs, signal(db, theirs)).json()

        mine = member(db, organisation, Role.EXECUTIVE)
        response = client.get(f"{BASE}/{other_action['id']}", headers=auth_header(mine))

        assert response.status_code == 404


class TestItAppearsInTheIntelligenceLayer:
    def test_the_register_is_countable_and_reconciles(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """Connecting decisions to intelligence means the decisions are counted too."""
        for _ in range(2):
            raise_action(client, owner, organisation, signal(db, organisation))

        overview = client.get("/api/v1/intelligence/overview", headers=auth_header(owner)).json()
        figure = next(f for f in overview["figures"] if f["label"] == "Actions")

        assert figure["value"] == 2

        basis = {k: v for k, v in figure["basis"].items() if v is not None}
        drilled = client.get(
            "/api/v1/intelligence/records", params=basis, headers=auth_header(owner)
        ).json()
        assert drilled["total"] == 2

    def test_actions_waiting_show_up_as_unresolved(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        raise_action(client, owner, organisation, signal(db, organisation))

        unresolved = client.get(
            "/api/v1/intelligence/unresolved", headers=auth_header(owner)
        ).json()
        waiting = next(
            f for f in unresolved["figures"] if f["label"] == "Actions proposed and not accepted"
        )

        assert waiting["value"] == 1

    def test_the_decision_trail_is_in_the_change_feed(
        self, client: TestClient, db: Session, owner: User, organisation: Organisation
    ):
        """What was decided, when, and by whom — the same mechanism as every record."""
        action_id = raise_action(client, owner, organisation, signal(db, organisation)).json()["id"]
        client.post(f"{BASE}/{action_id}/accept", headers=auth_header(owner))

        feed = client.get(
            "/api/v1/intelligence/changes",
            params={"measure": "actions"},
            headers=auth_header(owner),
        ).json()

        assert feed["total"] == 2
        assert {f["label"] for f in feed["by_action"]} == {"created", "accepted"}
        assert feed["data"][0]["actor"] == f"{owner.first_name} {owner.last_name}"
