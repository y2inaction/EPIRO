"""Intelligence and dashboards (spec sections 21-22).

Two properties these tests hold, and they are the whole point of the layer.

**Every figure reconciles with its own drill-down.** Spec section 4 requires
intelligence to be explainable and source-linked. A number on a dashboard is
explainable only if the records behind it can be produced, so the central test
here takes every figure the overview serves, hands its basis straight back to
``/intelligence/records``, and asserts the totals match. A figure that stopped
reconciling would be a figure nobody could check.

**A bucket too small to be anything but a person is suppressed.** Questions
come from the public. A breakdown that says one person in this ward asked about
this category is a step from saying who. Below the minimum cell size the count
is withheld — but a zero is still a zero, because "nobody asked" is not
sensitive and hiding it would make the breakdown unreadable.
"""

import uuid
from datetime import timedelta
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import audit
from app.models import (
    EvidenceStatus,
    GeographyLevel,
    Organisation,
    Question,
    QuestionStatus,
    Role,
    ThematicArea,
    User,
    VerificationState,
)
from app.services import intelligence
from tests.conftest import (
    auth_header,
    make_area,
    make_evidence,
    make_organisation,
    member,
)

BASE = "/api/v1/intelligence"


@pytest.fixture
def analyst(db: Session, organisation: Organisation) -> User:
    """Someone who reads the dashboard."""
    return member(db, organisation, Role.ANALYST)


def make_thematic_area(db: Session) -> ThematicArea:
    """A theme to filter on."""
    suffix = uuid.uuid4().hex[:8]
    theme = ThematicArea(name=f"Theme {suffix}", code=f"th-{suffix}")
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return theme


def ask(db: Session, organisation: Organisation, **overrides: Any) -> Question:
    """A question from the public, already claimed by this body."""
    fields: Dict[str, Any] = {
        "organisation_id": organisation.id,
        "question_text": f"When will the work at {uuid.uuid4().hex[:6]} finish?",
        "status": QuestionStatus.TRIAGED,
        "category": "water",
    }
    fields.update(overrides)
    question = Question(**fields)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


# --- Explainability --------------------------------------------------------


class TestEveryFigureIsCheckable:
    def test_every_overview_figure_reconciles_with_its_drill_down(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """The property that makes the dashboard explainable rather than asserted.

        Spec section 4: intelligence must be explainable and source-linked.
        This takes each figure's own basis, fetches the records it describes,
        and asserts the totals agree.
        """
        for _ in range(3):
            make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        make_evidence(db, organisation, status=EvidenceStatus.DRAFT)
        for _ in range(6):
            ask(db, organisation)

        overview = client.get(f"{BASE}/overview", headers=auth_header(analyst)).json()
        assert overview["figures"], "the overview served no figures at all"

        for figure in overview["figures"]:
            basis = {k: v for k, v in figure["basis"].items() if v is not None}
            drilled = client.get(
                f"{BASE}/records", params=basis, headers=auth_header(analyst)
            ).json()

            expected = figure["value"]
            if figure["suppressed"]:
                # A suppressed figure still has to reconcile; it is the
                # published number that is withheld, not the underlying truth.
                assert drilled["total"] < intelligence.MIN_CELL_SIZE
            else:
                assert drilled["total"] == expected, (
                    f"figure '{figure['label']}' said {expected} but its own "
                    f"basis returned {drilled['total']}"
                )

    def test_a_drill_down_returns_the_basis_it_was_given(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)

        drilled = client.get(
            f"{BASE}/records",
            params={"measure": "evidence", "dimension": "status", "value": "published"},
            headers=auth_header(analyst),
        ).json()

        assert drilled["basis"]["measure"] == "evidence"
        assert drilled["basis"]["dimension"] == "status"
        assert drilled["basis"]["value"] == "published"

    def test_every_breakdown_bucket_reconciles_too(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        for _ in range(2):
            make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        for _ in range(3):
            make_evidence(db, organisation, status=EvidenceStatus.DRAFT)

        breakdown = client.get(
            f"{BASE}/breakdown",
            params={"measure": "evidence", "dimension": "status"},
            headers=auth_header(analyst),
        ).json()

        for figure in breakdown["figures"]:
            basis = {k: v for k, v in figure["basis"].items() if v is not None}
            drilled = client.get(
                f"{BASE}/records", params=basis, headers=auth_header(analyst)
            ).json()
            assert drilled["total"] == figure["value"]

    def test_the_drill_down_actually_returns_rows(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """A total that agrees but returns nothing would be no use."""
        record = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)

        drilled = client.get(
            f"{BASE}/records",
            params={"measure": "evidence", "dimension": "status", "value": "published"},
            headers=auth_header(analyst),
        ).json()

        assert [row["id"] for row in drilled["data"]] == [str(record.id)]


# --- Suppression -----------------------------------------------------------


class TestSuppression:
    def test_a_small_bucket_of_questions_is_withheld(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """One person asking about a category must not be reported as one."""
        ask(db, organisation, category="sanitation")

        breakdown = client.get(
            f"{BASE}/breakdown",
            params={"measure": "questions", "dimension": "category"},
            headers=auth_header(analyst),
        ).json()

        bucket = next(f for f in breakdown["figures"] if f["label"] == "sanitation")
        assert bucket["suppressed"] is True
        assert bucket["value"] is None
        assert breakdown["suppressed_buckets"] == 1

    def test_a_suppressed_bucket_cannot_be_recovered_by_subtraction(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """Primary suppression alone is defeated by arithmetic.

        With eight water, five roads and two sanitation, withholding only
        sanitation leaves 15 - 8 - 5 = 2 — exactly the number the threshold
        existed to hide. A second bucket has to go with it.
        """
        for _ in range(8):
            ask(db, organisation, category="water")
        for _ in range(5):
            ask(db, organisation, category="roads")
        for _ in range(2):
            ask(db, organisation, category="sanitation")

        overview = client.get(f"{BASE}/overview", headers=auth_header(analyst)).json()
        total = next(f for f in overview["figures"] if f["label"] == "Questions from the public")[
            "value"
        ]

        breakdown = client.get(
            f"{BASE}/breakdown",
            params={"measure": "questions", "dimension": "category"},
            headers=auth_header(analyst),
        ).json()

        reported = [f["value"] for f in breakdown["figures"] if not f["suppressed"]]
        withheld = [f for f in breakdown["figures"] if f["suppressed"]]

        # The property: the residual left by subtraction is shared between at
        # least two withheld buckets, so it cannot be attributed to either.
        assert len(withheld) >= 2, (
            "a single withheld bucket is recoverable: "
            f"{total} - {sum(reported)} = {total - sum(reported)}"
        )
        assert total - sum(reported) == 7, "the residual covers sanitation and roads together"

    def test_a_bucket_at_the_threshold_is_reported(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        for _ in range(intelligence.MIN_CELL_SIZE):
            ask(db, organisation, category="roads")

        breakdown = client.get(
            f"{BASE}/breakdown",
            params={"measure": "questions", "dimension": "category"},
            headers=auth_header(analyst),
        ).json()

        bucket = next(f for f in breakdown["figures"] if f["label"] == "roads")
        assert bucket["suppressed"] is False
        assert bucket["value"] == intelligence.MIN_CELL_SIZE

    def test_a_zero_is_reported_as_zero(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """ "Nobody asked" and "too few asked to say" are different facts."""
        overview = client.get(f"{BASE}/overview", headers=auth_header(analyst)).json()

        questions = next(
            f for f in overview["figures"] if f["label"] == "Questions from the public"
        )
        assert questions["value"] == 0
        assert questions["suppressed"] is False

    def test_evidence_is_never_suppressed(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """Hiding "three boreholes here" would conceal public information.

        Suppression protects people, not public works. Applying it to evidence
        would make the platform less transparent in the name of privacy that is
        not at stake.
        """
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)

        breakdown = client.get(
            f"{BASE}/breakdown",
            params={"measure": "evidence", "dimension": "status"},
            headers=auth_header(analyst),
        ).json()

        assert breakdown["suppressed_buckets"] == 0
        assert all(f["value"] is not None for f in breakdown["figures"])

    def test_the_measures_endpoint_says_which_measures_suppress(
        self, client: TestClient, analyst: User
    ):
        """So a client can explain a blank rather than just showing one."""
        listed = client.get(f"{BASE}/measures", headers=auth_header(analyst)).json()

        by_name = {m["name"]: m for m in listed["measures"]}
        assert by_name["questions"]["suppressed_below_minimum"] is True
        assert by_name["evidence"]["suppressed_below_minimum"] is False
        assert listed["minimum_cell_size"] == intelligence.MIN_CELL_SIZE

    def test_the_suppression_rule_is_stated_in_the_response(
        self, client: TestClient, analyst: User
    ):
        overview = client.get(f"{BASE}/overview", headers=auth_header(analyst)).json()

        assert str(intelligence.MIN_CELL_SIZE) in overview["suppression_note"]
        assert overview["minimum_cell_size"] == intelligence.MIN_CELL_SIZE


# --- What cannot be asked --------------------------------------------------


class TestClosedDimensions:
    def test_an_arbitrary_column_cannot_be_grouped_by(self, client: TestClient, analyst: User):
        """A dimension must not become a route to a field nobody meant to aggregate."""
        response = client.get(
            f"{BASE}/breakdown",
            params={"measure": "questions", "dimension": "submitter_email"},
            headers=auth_header(analyst),
        )

        assert response.status_code == 400
        assert "cannot be broken down by" in response.json()["detail"]

    def test_no_measure_offers_a_dimension_that_identifies_a_person(self):
        """Asserted against the registry itself.

        Spec section 4 forbids profiling. The dimensions are a closed set, and
        this fails if somebody adds one that groups people rather than records.
        """
        forbidden = {
            "submitter_email",
            "created_by",
            "reported_by",
            "assigned_to",
            "responded_by",
            "raised_by",
            "user_id",
            "is_anonymous",
        }
        for measure in intelligence.MEASURES.values():
            offending = set(measure.dimensions) & forbidden
            assert offending == set(), f"{measure.name} offers {offending}"

    def test_an_unknown_measure_names_the_ones_that_exist(self, client: TestClient, analyst: User):
        """A 400 that does not say what would have worked is a dead end."""
        response = client.get(
            f"{BASE}/breakdown",
            params={"measure": "voters", "dimension": "status"},
            headers=auth_header(analyst),
        )

        assert response.status_code == 400
        assert "evidence" in response.json()["detail"]


# --- Tenancy ---------------------------------------------------------------


class TestTenancy:
    def test_the_overview_counts_only_the_caller_s_organisations(
        self,
        client: TestClient,
        db: Session,
        analyst: User,
        outsider: User,
        organisation: Organisation,
    ):
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)

        mine = client.get(f"{BASE}/overview", headers=auth_header(analyst)).json()
        theirs = client.get(f"{BASE}/overview", headers=auth_header(outsider)).json()

        def figure(payload, label):
            return next(f for f in payload["figures"] if f["label"] == label)

        assert figure(mine, "Evidence records")["value"] == 1
        assert figure(theirs, "Evidence records")["value"] == 0

    def test_a_drill_down_cannot_reach_further_than_the_figure(
        self,
        client: TestClient,
        db: Session,
        outsider: User,
        organisation: Organisation,
    ):
        """Otherwise the explainability mechanism would be a way round scoping."""
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)

        drilled = client.get(
            f"{BASE}/records",
            params={"measure": "evidence"},
            headers=auth_header(outsider),
        ).json()

        assert drilled["total"] == 0
        assert drilled["data"] == []

    def test_a_second_organisations_records_do_not_leak_into_a_breakdown(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        other = make_organisation(db)
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        for _ in range(4):
            make_evidence(db, other, status=EvidenceStatus.PUBLISHED)

        breakdown = client.get(
            f"{BASE}/breakdown",
            params={"measure": "evidence", "dimension": "status"},
            headers=auth_header(analyst),
        ).json()

        published = next(f for f in breakdown["figures"] if f["label"] == "published")
        assert published["value"] == 1


# --- Geography -------------------------------------------------------------


class TestGeography:
    def test_an_area_filter_covers_everything_beneath_it(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """Matching how search resolves the same filter."""
        state = make_area(db, GeographyLevel.STATE)
        lga = make_area(db, GeographyLevel.LGA, parent=state)
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED, geography_id=lga.id)

        overview = client.get(
            f"{BASE}/overview",
            params={"geography_id": str(state.id)},
            headers=auth_header(analyst),
        ).json()

        evidence = next(f for f in overview["figures"] if f["label"] == "Evidence records")
        assert evidence["value"] == 1

    def test_an_area_filter_excludes_what_is_outside_it(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        inside = make_area(db, GeographyLevel.STATE)
        outside = make_area(db, GeographyLevel.STATE)
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED, geography_id=outside.id)

        overview = client.get(
            f"{BASE}/overview",
            params={"geography_id": str(inside.id)},
            headers=auth_header(analyst),
        ).json()

        evidence = next(f for f in overview["figures"] if f["label"] == "Evidence records")
        assert evidence["value"] == 0

    def test_the_area_filter_survives_the_round_trip_to_the_drill_down(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """A basis that dropped its geography would reconcile against the wrong set."""
        inside = make_area(db, GeographyLevel.STATE)
        outside = make_area(db, GeographyLevel.STATE)
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED, geography_id=inside.id)
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED, geography_id=outside.id)

        overview = client.get(
            f"{BASE}/overview",
            params={"geography_id": str(inside.id)},
            headers=auth_header(analyst),
        ).json()
        figure = next(f for f in overview["figures"] if f["label"] == "Evidence records")

        basis = {k: v for k, v in figure["basis"].items() if v is not None}
        drilled = client.get(f"{BASE}/records", params=basis, headers=auth_header(analyst)).json()

        assert figure["value"] == 1
        assert drilled["total"] == 1


# --- Filters ---------------------------------------------------------------


class TestFilters:
    """The six filters, and the rule that a filter is never quietly dropped."""

    def test_a_filtered_figure_still_reconciles_with_its_own_drill_down(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """The property that makes a filter safe rather than decorative.

        If a filter narrowed the count but did not reach the basis, the figure
        would count one set of records and its own link would open another.
        """
        theme = make_thematic_area(db)
        for _ in range(3):
            make_evidence(db, organisation, thematic_area_id=theme.id)
        make_evidence(db, organisation)

        overview = client.get(
            f"{BASE}/overview",
            params={"thematic_area_id": str(theme.id)},
            headers=auth_header(analyst),
        ).json()

        for figure in overview["figures"]:
            basis = {k: v for k, v in figure["basis"].items() if v is not None}
            assert basis["thematic_area_id"] == str(theme.id), (
                f"figure '{figure['label']}' was narrowed by a theme its basis " "did not carry"
            )

            drilled = client.get(
                f"{BASE}/records", params=basis, headers=auth_header(analyst)
            ).json()
            if not figure["suppressed"]:
                assert drilled["total"] == figure["value"]

    def test_a_filter_a_measure_cannot_honour_is_refused_not_ignored(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """Ignoring it would serve an unfiltered count under a filtered heading.

        That is wrong in the one way nobody checks, because it looks exactly
        like the right answer.
        """
        response = client.get(
            f"{BASE}/breakdown",
            params={
                "measure": "questions",
                "dimension": "category",
                "verification_status": "verified",
            },
            headers=auth_header(analyst),
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "verification_status" in detail
        # A refusal that does not say what would have worked is a dead end.
        assert "status" in detail

    def test_the_catalogue_says_which_filters_each_measure_takes(
        self, client: TestClient, analyst: User
    ):
        """So a client offers only the filters that work, rather than finding out."""
        catalogue = client.get(f"{BASE}/measures", headers=auth_header(analyst)).json()
        by_name = {m["name"]: m for m in catalogue["measures"]}

        assert "verification_status" in by_name["evidence"]["filters"]
        assert "verification_status" not in by_name["questions"]["filters"]
        assert "thematic_area_id" not in by_name["questions"]["filters"]
        # Every measure carries an organisation and a creation date.
        for measure in catalogue["measures"]:
            assert {"organisation_id", "since", "until"} <= set(measure["filters"])

    def test_a_mixed_list_names_the_measures_a_filter_forced_it_to_drop(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """A missing figure and a figure that counted nothing mean opposite things."""
        make_evidence(db, organisation)

        overview = client.get(
            f"{BASE}/overview",
            params={"verification_status": "verified"},
            headers=auth_header(analyst),
        ).json()

        assert "questions" in overview["excluded_measures"]
        assert all(f["basis"]["measure"] == "evidence" for f in overview["figures"])

    def test_the_date_range_includes_the_whole_closing_day(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """An off-by-one here silently drops a day of records."""
        record = make_evidence(db, organisation)
        today = record.created_at.date()

        counted = client.get(
            f"{BASE}/records",
            params={"measure": "evidence", "since": str(today), "until": str(today)},
            headers=auth_header(analyst),
        ).json()

        assert counted["total"] == 1

    def test_a_date_range_before_the_records_counts_none_of_them(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        record = make_evidence(db, organisation)
        before = record.created_at.date() - timedelta(days=2)

        counted = client.get(
            f"{BASE}/records",
            params={"measure": "evidence", "until": str(before)},
            headers=auth_header(analyst),
        ).json()

        assert counted["total"] == 0

    def test_an_organisation_filter_narrows_and_never_widens(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Naming another body's id must not reach into it."""
        other = make_organisation(db)
        make_evidence(db, other)
        mine = member(db, organisation, Role.ANALYST)
        make_evidence(db, organisation)

        counted = client.get(
            f"{BASE}/records",
            params={"measure": "evidence", "organisation_id": str(other.id)},
            headers=auth_header(mine),
        ).json()

        assert counted["total"] == 0


# --- What remains unresolved -----------------------------------------------


class TestUnresolved:
    def test_it_counts_open_states_and_each_one_reconciles(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        make_evidence(db, organisation, verification_status=VerificationState.UNVERIFIED)
        make_evidence(db, organisation, verification_status=VerificationState.VERIFIED)

        response = client.get(f"{BASE}/unresolved", headers=auth_header(analyst)).json()
        waiting = next(
            f for f in response["figures"] if f["label"] == "Evidence nobody has checked yet"
        )

        assert waiting["value"] == 1

        basis = {k: v for k, v in waiting["basis"].items() if v is not None}
        drilled = client.get(f"{BASE}/records", params=basis, headers=auth_header(analyst)).json()
        assert drilled["total"] == 1

    def test_every_unresolved_figure_is_a_single_value_basis(
        self, client: TestClient, analyst: User
    ):
        """So each one drills down to exactly the records it counted.

        A broader definition would read better in a heading and could not be
        checked against its own rows.
        """
        response = client.get(f"{BASE}/unresolved", headers=auth_header(analyst)).json()

        assert response["figures"]
        for figure in response["figures"]:
            assert figure["basis"]["dimension"], f"{figure['label']} groups by nothing"
            assert figure["basis"]["value"], f"{figure['label']} names no open state"


# --- What is deliberately not offered --------------------------------------


class TestNoFilterNarrowsByAPerson:
    def test_no_filter_names_a_person(self):
        """Spec section 4, applied to staff as well as citizens.

        Who verified a record is on that record's approval trail, where it is
        accountability. The same fact as a filter over aggregates is a league
        table of staff, and this layer does not offer one.
        """
        forbidden = {
            "created_by",
            "updated_by",
            "assigned_to",
            "reviewer_id",
            "verified_by",
            "approved_by",
            "reported_by",
            "user_id",
            "owner",
            "lead_id",
            "submitter_email",
        }

        assert not forbidden & set(intelligence.FILTER_COLUMNS)

    def test_no_measure_can_be_filtered_by_a_person(self):
        for measure in intelligence.MEASURES.values():
            for name in intelligence.supported_filters(measure):
                assert not name.endswith("_by"), (
                    f"'{measure.name}' offers a filter named '{name}', which "
                    "narrows aggregates by a person"
                )


# --- Temporal intelligence -------------------------------------------------


class TestChanges:
    """What changed, when, where, on what evidence, and by whom."""

    def test_it_reports_what_changed_and_who_did_it(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        record = make_evidence(db, organisation)
        audit.record(
            db,
            action=audit.VERIFIED,
            entity_type="evidence",
            entity_id=record.id,
            user=analyst,
            organisation_id=organisation.id,
            evidence_id=record.id,
            old_values={"verification_status": "unverified"},
            new_values={"verification_status": "verified"},
        )

        feed = client.get(
            f"{BASE}/changes", params={"measure": "evidence"}, headers=auth_header(analyst)
        ).json()

        assert feed["total"] == 1
        entry = feed["data"][0]
        assert entry["action"] == "verified"
        assert entry["entity_label"] == record.title
        assert entry["actor"] == f"{analyst.first_name} {analyst.last_name}"
        assert entry["evidence_id"] == str(record.id)
        assert entry["changed"] == [
            {
                "field": "verification_status",
                "from": "unverified",
                "to": "verified",
                "had_previous": True,
            }
        ]

    def test_the_date_range_narrows_when_the_change_happened(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """Not when the record was created, which is what it means everywhere else.

        A record added in June and verified in September is a September
        change. Applying the record's own date here would answer a different
        question than the one the feed is for.
        """
        record = make_evidence(db, organisation)
        entry = audit.record(
            db,
            action=audit.VERIFIED,
            entity_type="evidence",
            entity_id=record.id,
            user=analyst,
            organisation_id=organisation.id,
        )
        entry.created_at = entry.created_at + timedelta(days=30)
        db.commit()

        when = entry.created_at.date()

        inside = client.get(
            f"{BASE}/changes",
            params={"measure": "evidence", "since": str(when), "until": str(when)},
            headers=auth_header(analyst),
        ).json()
        before = client.get(
            f"{BASE}/changes",
            params={"measure": "evidence", "until": str(when - timedelta(days=1))},
            headers=auth_header(analyst),
        ).json()

        assert inside["total"] == 1
        assert before["total"] == 0

    def test_where_it_changed_is_resolved_through_the_record(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """An audit entry carries no area of its own."""
        inside = make_area(db, GeographyLevel.STATE)
        outside = make_area(db, GeographyLevel.STATE)
        here = make_evidence(db, organisation, geography_id=inside.id)
        there = make_evidence(db, organisation, geography_id=outside.id)

        for record in (here, there):
            audit.record(
                db,
                action=audit.APPROVED,
                entity_type="evidence",
                entity_id=record.id,
                user=analyst,
                organisation_id=organisation.id,
            )

        feed = client.get(
            f"{BASE}/changes",
            params={"measure": "evidence", "geography_id": str(inside.id)},
            headers=auth_header(analyst),
        ).json()

        assert feed["total"] == 1
        assert feed["data"][0]["entity_id"] == str(here.id)

    def test_the_summary_by_action_reconciles_with_the_feed(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """A change figure has to be checkable, like every other figure here."""
        record = make_evidence(db, organisation)
        for action in (audit.VERIFIED, audit.APPROVED, audit.APPROVED):
            audit.record(
                db,
                action=action,
                entity_type="evidence",
                entity_id=record.id,
                user=analyst,
                organisation_id=organisation.id,
            )

        feed = client.get(
            f"{BASE}/changes", params={"measure": "evidence"}, headers=auth_header(analyst)
        ).json()

        for figure in feed["by_action"]:
            narrowed = client.get(
                f"{BASE}/changes",
                params={"measure": "evidence", "action": figure["basis"]["value"]},
                headers=auth_header(analyst),
            ).json()
            assert narrowed["total"] == figure["value"], (
                f"'{figure['label']}' said {figure['value']} but narrowing to it "
                f"returned {narrowed['total']}"
            )

    def test_it_never_reaches_another_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        theirs = make_evidence(db, other)
        stranger = member(db, other, Role.ANALYST)
        audit.record(
            db,
            action=audit.APPROVED,
            entity_type="evidence",
            entity_id=theirs.id,
            user=stranger,
            organisation_id=other.id,
        )
        mine = member(db, organisation, Role.ANALYST)

        feed = client.get(
            f"{BASE}/changes", params={"measure": "evidence"}, headers=auth_header(mine)
        ).json()

        assert feed["total"] == 0

    def test_the_feed_cannot_be_narrowed_or_grouped_by_a_person(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """Naming the actor per entry is accountability. Aggregating is not.

        Spec section 39 requires a trail that can answer for a decision, so an
        entry names who acted. Turning that into a filter or a grouping would
        make it a productivity report on staff, which section 4's prohibition
        on profiling rules out just as it does for citizens.
        """
        record = make_evidence(db, organisation)
        audit.record(
            db,
            action=audit.APPROVED,
            entity_type="evidence",
            entity_id=record.id,
            user=analyst,
            organisation_id=organisation.id,
        )

        # An actor filter is not accepted: it is ignored as an unknown query
        # parameter rather than narrowing anything.
        both = client.get(
            f"{BASE}/changes",
            params={"measure": "evidence", "user_id": str(uuid.uuid4())},
            headers=auth_header(analyst),
        ).json()
        assert both["total"] == 1

        feed = client.get(
            f"{BASE}/changes", params={"measure": "evidence"}, headers=auth_header(analyst)
        ).json()
        for figure in feed["by_action"]:
            assert figure["basis"]["dimension"] == "action"

    def test_an_unrecorded_previous_value_is_not_reported_as_empty(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        """The transition endpoints record what a record became, not what it was.

        Reporting the absent key as null made the feed say "verification
        status: not set → verified" about a record that had been sitting at
        "unverified" — an assertion the trail never made.
        """
        record = make_evidence(db, organisation)
        audit.record(
            db,
            action=audit.VERIFIED,
            entity_type="evidence",
            entity_id=record.id,
            user=analyst,
            organisation_id=organisation.id,
            new_values={"verification_status": "verified"},
        )

        feed = client.get(
            f"{BASE}/changes", params={"measure": "evidence"}, headers=auth_header(analyst)
        ).json()

        assert feed["data"][0]["changed"] == [
            {
                "field": "verification_status",
                "from": None,
                "to": "verified",
                "had_previous": False,
            }
        ]

    def test_a_previous_value_that_really_was_empty_says_so(
        self, client: TestClient, db: Session, analyst: User, organisation: Organisation
    ):
        record = make_evidence(db, organisation)
        audit.record(
            db,
            action=audit.UPDATED,
            entity_type="evidence",
            entity_id=record.id,
            user=analyst,
            organisation_id=organisation.id,
            old_values={"outcome": None},
            new_values={"outcome": "Twelve boreholes in service."},
        )

        feed = client.get(
            f"{BASE}/changes", params={"measure": "evidence"}, headers=auth_header(analyst)
        ).json()

        assert feed["data"][0]["changed"][0]["had_previous"] is True
