"""Global search tests.

Covers spec section 35: one search across the content types that exist, with
the eight filters it names, and matching that an index can actually serve.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import EvidenceStatus, GeographyLevel, Organisation, Role, ThematicArea
from tests.conftest import (
    auth_header,
    make_area,
    make_area_chain,
    make_evidence,
    make_organisation,
    make_source,
    make_story,
    member,
)
from tests.test_projects import make_project


def search(client: TestClient, user, **params) -> dict:
    """Run a search as a user and return the body."""
    response = client.get("/api/v1/search/", params=params, headers=auth_header(user))
    assert response.status_code == 200, response.text
    return response.json()


def make_theme(db: Session) -> ThematicArea:
    """Create a thematic area to filter on."""
    import uuid

    suffix = uuid.uuid4().hex[:8]
    theme = ThematicArea(name=f"Theme {suffix}", code=f"th-{suffix}")
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return theme


class TestMatching:
    def test_a_word_in_the_title_is_found(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole rehabilitation in Kano")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole")

        assert [item["title"] for item in body["evidence"]] == ["Borehole rehabilitation in Kano"]
        assert body["total"] == 1

    def test_a_word_in_the_description_is_found(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(
            db,
            organisation,
            title="Water programme",
            description="Twelve boreholes were drilled and handed over.",
        )
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="drilled")

        assert len(body["evidence"]) == 1

    def test_matching_is_stemmed(self, client: TestClient, db: Session, organisation: Organisation):
        """A search for the plural must find the singular: ILIKE could not."""
        make_evidence(db, organisation, title="Clinic rebuilt after flooding")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="flood")

        assert len(body["evidence"]) == 1

    def test_a_partial_word_matches_as_a_prefix(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Type-ahead: a half-typed word still finds the record."""
        make_evidence(db, organisation, title="Borehole rehabilitation")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="boreh")

        assert len(body["evidence"]) == 1

    def test_all_terms_must_match(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole rehabilitation")
        make_evidence(db, organisation, title="Clinic rehabilitation")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="clinic rehabilitation")

        assert [item["title"] for item in body["evidence"]] == ["Clinic rehabilitation"]

    def test_a_quoted_phrase_matches_only_in_order(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Rehabilitation of a borehole")
        make_evidence(db, organisation, title="Borehole rehabilitation completed")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q='"borehole rehabilitation"')

        assert [item["title"] for item in body["evidence"]] == ["Borehole rehabilitation completed"]

    def test_a_title_hit_outranks_a_body_mention(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(
            db,
            organisation,
            title="Unrelated works",
            description="A passing mention of a borehole, nothing more.",
        )
        make_evidence(db, organisation, title="Borehole programme")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole")

        assert body["evidence"][0]["title"] == "Borehole programme"

    def test_the_permanent_reference_is_searchable(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """An evidence record must be findable by the reference it is cited by."""
        evidence = make_evidence(db, organisation, title="Clinic handover")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q=evidence.reference)

        assert [item["id"] for item in body["evidence"]] == [str(evidence.id)]

    def test_a_query_that_matches_nothing_returns_nothing(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole rehabilitation")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="aquaculture")

        assert body["total"] == 0
        assert body["evidence"] == []


class TestContentTypes:
    def test_search_covers_stories_projects_and_questions(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, title="Borehole evidence")
        make_story(db, evidence, title="Borehole story", body="A borehole was rehabilitated.")
        make_project(db, organisation, name="Borehole project")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole")

        assert len(body["evidence"]) == 1
        assert len(body["stories"]) == 1
        assert len(body["projects"]) == 1
        assert body["total"] == 3

    def test_content_type_narrows_the_search(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        evidence = make_evidence(db, organisation, title="Borehole evidence")
        make_story(db, evidence, title="Borehole story", body="Body.")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", content_type="story")

        assert len(body["stories"]) == 1
        assert body["evidence"] == []
        assert body["total"] == 1

    def test_an_unknown_content_type_returns_nothing(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole evidence")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", content_type="unicorn")

        assert body["total"] == 0

    def test_the_response_names_the_types_that_do_not_exist_yet(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Spec section 35 lists more than is built; the gap is stated, not hidden."""
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole")

        assert "documents" in body["unsearchable_types"]
        assert "stakeholders" in body["unsearchable_types"]


class TestFilters:
    def test_filtering_by_date_range(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole early", evidence_date=date(2026, 1, 10))
        make_evidence(db, organisation, title="Borehole late", evidence_date=date(2026, 8, 10))
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", date_from="2026-06-01", date_to="2026-12-31")

        assert [item["title"] for item in body["evidence"]] == ["Borehole late"]

    def test_filtering_by_geography_includes_everything_beneath_it(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """ "Everything in this state" must reach records pinned to its wards."""
        chain = make_area_chain(db)
        make_evidence(db, organisation, title="Borehole in the LGA", geography_id=chain["lga"].id)
        elsewhere = make_area(db, GeographyLevel.COUNTRY)
        make_evidence(db, organisation, title="Borehole elsewhere", geography_id=elsewhere.id)
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", geography_id=str(chain["state"].id))

        assert [item["title"] for item in body["evidence"]] == ["Borehole in the LGA"]

    def test_filtering_by_theme(self, client: TestClient, db: Session, organisation: Organisation):
        theme = make_theme(db)
        make_evidence(db, organisation, title="Borehole themed", thematic_area_id=theme.id)
        make_evidence(db, organisation, title="Borehole unthemed")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", thematic_area_id=str(theme.id))

        assert [item["title"] for item in body["evidence"]] == ["Borehole themed"]

    def test_filtering_by_source(self, client: TestClient, db: Session, organisation: Organisation):
        source = make_source(db, organisation)
        make_evidence(db, organisation, source=source, title="Borehole cited")
        make_evidence(db, organisation, title="Borehole other")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", source_id=str(source.id))

        assert [item["title"] for item in body["evidence"]] == ["Borehole cited"]

    def test_filtering_by_status(self, client: TestClient, db: Session, organisation: Organisation):
        make_evidence(db, organisation, title="Borehole published", status=EvidenceStatus.PUBLISHED)
        make_evidence(db, organisation, title="Borehole draft")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", status="published")

        assert [item["title"] for item in body["evidence"]] == ["Borehole published"]

    def test_filtering_by_verification(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole checked", verification_status="verified")
        make_evidence(db, organisation, title="Borehole unchecked")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", verification_status="verified")

        assert [item["title"] for item in body["evidence"]] == ["Borehole checked"]

    def test_filtering_by_owner(self, client: TestClient, db: Session, organisation: Organisation):
        author = member(db, organisation, Role.RESEARCHER)
        make_evidence(db, organisation, title="Borehole mine", created_by=author.id)
        make_evidence(db, organisation, title="Borehole theirs")

        body = search(client, author, q="borehole", owner_id=str(author.id))

        assert [item["title"] for item in body["evidence"]] == ["Borehole mine"]

    def test_filtering_by_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        reader = member(db, organisation, Role.RESEARCHER)
        from tests.conftest import grant_role

        grant_role(db, reader, other, Role.RESEARCHER)

        make_evidence(db, organisation, title="Borehole here")
        make_evidence(db, other, title="Borehole there")

        body = search(client, reader, q="borehole", organisation_id=str(other.id))

        assert [item["title"] for item in body["evidence"]] == ["Borehole there"]

    def test_an_organisation_filter_cannot_widen_access(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Filtering by someone else's organisation must not reveal it."""
        other = make_organisation(db)
        make_evidence(db, other, title="Borehole theirs")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", organisation_id=str(other.id))

        assert body["total"] == 0

    def test_a_type_that_cannot_express_a_filter_is_left_out(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A project has no source, so it must not appear in a source-filtered search.

        Returning it unfiltered would present it as matching a filter that was
        never applied to it.
        """
        source = make_source(db, organisation)
        make_evidence(db, organisation, source=source, title="Borehole evidence")
        make_project(db, organisation, name="Borehole project")
        reader = member(db, organisation, Role.RESEARCHER)

        body = search(client, reader, q="borehole", source_id=str(source.id))

        assert len(body["evidence"]) == 1
        assert body["projects"] == []
        assert body["total"] == 1


class TestTenancy:
    def test_another_tenants_content_is_not_returned(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        make_evidence(db, organisation, title="Borehole rehabilitation")
        stranger = member(db, make_organisation(db), Role.RESEARCHER)

        body = search(client, stranger, q="borehole")

        assert body["total"] == 0

    def test_a_user_in_no_organisation_sees_nothing(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        from tests.conftest import make_user

        make_evidence(db, organisation, title="Borehole rehabilitation")
        outsider = make_user(db)

        body = search(client, outsider, q="borehole")

        assert body["total"] == 0


class TestIndexIsUsable:
    def test_the_evidence_search_can_be_served_by_its_index(self, db: Session):
        """The point of the change: the query plan can use an index.

        The previous ILIKE '%term%' could not be served by any index at all, so
        every search was a sequential scan. Sequential scans are disabled for
        this one statement because the test tables are far too small for the
        planner to choose the index on cost; what is being asserted is that the
        index *can* answer the query, which is what changed.
        """
        db.execute(text("SET LOCAL enable_seqscan = off"))

        plan = db.execute(
            text(
                "EXPLAIN SELECT id FROM evidence "
                "WHERE search_vector @@ to_tsquery('english', 'borehole:*')"
            )
        ).scalars()

        assert "idx_evidence_search" in "\n".join(plan)
