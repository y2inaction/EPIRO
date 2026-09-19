"""Public portal tests.

Covers spec section 14. Three things are asserted throughout, because the
portal is the surface where a mistake is hardest to take back: only published
records appear, no internal field is served, and no individual is identified.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EvidenceStatus, Organisation, Question
from app.models import QuestionStatus as Q
from app.models import StoryStatus as S
from tests.conftest import make_evidence, make_organisation, make_story, make_user

# Fields that must never appear on the portal: internal workflow state and the
# identity of anyone who handled or submitted a record.
FORBIDDEN_FIELDS = (
    "created_by",
    "updated_by",
    "verified_by",
    "verifier_notes",
    "approved_by",
    "responded_by",
    "assigned_to",
    "submitter_email",
    "is_anonymous",
    "status",
    "approval_status",
    "metadata_json",
    "version",
)


def assert_no_internal_fields(payload) -> None:
    """Fail if a response carries anything internal, at any depth."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key not in FORBIDDEN_FIELDS, f"portal leaked {key}"
            assert_no_internal_fields(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_internal_fields(item)


def published_story(db: Session, organisation: Organisation, **overrides):
    """A story that completed the workflow and was published."""
    evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
    fields = {
        "status": S.PUBLISHED,
        "published_date": datetime.now(timezone.utc),
        "approved_by": make_user(db).id,
    }
    fields.update(overrides)
    return make_story(db, evidence, **fields)


def published_question(db: Session, organisation: Organisation, **overrides) -> Question:
    """A question whose answer was approved and published."""
    fields = {
        "question_text": f"Is the clinic open? {uuid.uuid4().hex[:8]}",
        "organisation_id": organisation.id,
        "status": Q.PUBLISHED,
        "is_published": True,
        "response": "Yes, it reopened in June.",
        "response_date": datetime.now(timezone.utc),
        "is_anonymous": False,
        "submitter_email": "asker@example.com",
        "responded_by": make_user(db).id,
    }
    fields.update(overrides)

    question = Question(**fields)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


class TestNoAuthenticationRequired:
    def test_the_portal_is_reachable_without_credentials(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Everything published was, until now, only reachable with a login."""
        published_story(db, organisation, title="Borehole rehabilitated")

        response = client.get("/api/v1/public/stories")

        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestOnlyPublishedContent:
    def test_a_draft_story_is_not_served(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        make_story(db, evidence, title="Still a draft", status=S.DRAFT)

        assert client.get("/api/v1/public/stories").json()["total"] == 0

    def test_a_story_awaiting_approval_is_not_served(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)
        make_story(db, evidence, title="Under review", status=S.IN_REVIEW)

        assert client.get("/api/v1/public/stories").json()["total"] == 0

    def test_a_withdrawn_story_disappears_from_the_portal(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Withdrawal is how something public is taken back."""
        story = published_story(db, organisation)
        assert client.get("/api/v1/public/stories").json()["total"] == 1

        story.status = S.ARCHIVED
        db.commit()

        assert client.get("/api/v1/public/stories").json()["total"] == 0

    def test_an_unpublished_story_is_reported_as_missing_not_forbidden(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The portal must not confirm that a draft exists."""
        evidence = make_evidence(db, organisation)
        story = make_story(db, evidence, status=S.DRAFT)

        response = client.get(f"/api/v1/public/stories/{story.id}")

        assert response.status_code == 404

    def test_unpublished_evidence_is_not_served(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, status=EvidenceStatus.APPROVED)

        assert client.get("/api/v1/public/evidence").json()["total"] == 0

    def test_a_question_with_an_unapproved_answer_is_not_served(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        published_question(db, organisation, status=Q.RESPONSE_DRAFTED, is_published=False)

        assert client.get("/api/v1/public/questions").json()["total"] == 0

    def test_search_does_not_reach_unpublished_content(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Nothing under review may be discovered by guessing search terms."""
        evidence = make_evidence(
            db, organisation, title="Confidential borehole finding", status=EvidenceStatus.DRAFT
        )
        make_story(db, evidence, title="Confidential borehole story", status=S.IN_REVIEW)

        body = client.get("/api/v1/public/search", params={"q": "borehole"}).json()

        assert body["total"] == 0


class TestNoLeakage:
    def test_a_story_carries_no_internal_fields(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        published_story(db, organisation, title="Borehole rehabilitated")

        body = client.get("/api/v1/public/stories").json()

        assert body["data"]
        assert_no_internal_fields(body)

    def test_evidence_carries_no_internal_fields(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(
            db,
            organisation,
            title="Borehole rehabilitated",
            status=EvidenceStatus.PUBLISHED,
            verified_by=make_user(db).id,
            verifier_notes="Checked against the register by phone.",
        )

        body = client.get("/api/v1/public/evidence").json()

        assert body["data"]
        assert_no_internal_fields(body)
        assert "Checked against the register" not in str(body)

    def test_a_question_never_identifies_the_person_who_asked(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Spec section 20: even a submitter who gave an address is not published."""
        published_question(db, organisation)

        body = client.get("/api/v1/public/questions").json()

        assert body["data"]
        assert_no_internal_fields(body)
        assert "asker@example.com" not in str(body)

    def test_search_results_carry_no_internal_fields(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        published_story(db, organisation, title="Borehole rehabilitated")
        make_evidence(db, organisation, title="Borehole evidence", status=EvidenceStatus.PUBLISHED)
        published_question(db, organisation, question_text="What about the borehole?")

        body = client.get("/api/v1/public/search", params={"q": "borehole"}).json()

        assert body["total"] == 3
        assert_no_internal_fields(body)


class TestCitation:
    def test_a_story_carries_the_reference_of_its_evidence(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A reader must be able to follow a claim back to its record."""
        story = published_story(db, organisation)

        body = client.get(f"/api/v1/public/stories/{story.id}").json()

        assert body["evidence_reference"] == story.evidence.reference

    def test_evidence_is_addressable_by_its_permanent_reference(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(
            db, organisation, title="Borehole rehabilitated", status=EvidenceStatus.PUBLISHED
        )

        response = client.get(f"/api/v1/public/evidence/{evidence.reference}")

        assert response.status_code == 200
        assert response.json()["reference"] == evidence.reference

    def test_an_unpublished_reference_is_not_resolvable(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, status=EvidenceStatus.APPROVED)

        response = client.get(f"/api/v1/public/evidence/{evidence.reference}")

        assert response.status_code == 404

    def test_evidence_shows_how_far_verification_got(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The reader is entitled to the state, never to who signed it off."""
        make_evidence(
            db,
            organisation,
            status=EvidenceStatus.PUBLISHED,
            verification_status="verified",
            verified_by=make_user(db).id,
        )

        record = client.get("/api/v1/public/evidence").json()["data"][0]

        assert record["verification_status"] == "verified"
        assert "verified_by" not in record


class TestFiltering:
    def test_stories_can_be_filtered_by_language(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        published_story(db, organisation, title="English story", language="en")
        published_story(db, organisation, title="Hausa story", language="ha")

        body = client.get("/api/v1/public/stories", params={"language": "ha"}).json()

        assert [item["title"] for item in body["data"]] == ["Hausa story"]

    def test_stories_can_be_filtered_to_the_featured_set(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        published_story(db, organisation, title="Featured", featured=True)
        published_story(db, organisation, title="Ordinary")

        body = client.get("/api/v1/public/stories", params={"featured_only": True}).json()

        assert [item["title"] for item in body["data"]] == ["Featured"]

    def test_evidence_can_be_filtered_by_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        make_evidence(db, organisation, title="Ours", status=EvidenceStatus.PUBLISHED)
        make_evidence(db, other, title="Theirs", status=EvidenceStatus.PUBLISHED)

        body = client.get(
            "/api/v1/public/evidence", params={"organisation_id": str(organisation.id)}
        ).json()

        assert [item["title"] for item in body["data"]] == ["Ours"]

    def test_evidence_is_returned_most_recent_first(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(
            db,
            organisation,
            title="Older",
            status=EvidenceStatus.PUBLISHED,
            evidence_date=date(2026, 1, 1),
        )
        make_evidence(
            db,
            organisation,
            title="Newer",
            status=EvidenceStatus.PUBLISHED,
            evidence_date=date(2026, 8, 1),
        )

        body = client.get("/api/v1/public/evidence").json()

        assert [item["title"] for item in body["data"]] == ["Newer", "Older"]


class TestOrganisations:
    def test_only_bodies_that_published_something_are_listed(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The portal should not enumerate tenants that publish nothing."""
        silent = make_organisation(db)
        make_evidence(db, organisation, status=EvidenceStatus.PUBLISHED)

        listed = client.get("/api/v1/public/organisations").json()

        names = [item["id"] for item in listed]
        assert str(organisation.id) in names
        assert str(silent.id) not in names
