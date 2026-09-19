"""Story editorial lifecycle tests.

Covers spec section 36 (review and approval sit between drafting and
publication, and every decision is recorded) and spec section 51 (public
information cannot be published without the required approval).
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ApprovalRecord, AuditLog, EvidenceStatus, Organisation, Role, Story
from app.models import StoryStatus as S
from tests.conftest import (
    auth_header,
    make_evidence,
    make_organisation,
    make_story,
    member,
)


def approved_evidence(db: Session, organisation: Organisation):
    """Evidence that has cleared approval, so a story on it may advance."""
    return make_evidence(db, organisation, status=EvidenceStatus.APPROVED)


def story_at(db: Session, organisation: Organisation, status: S, **overrides) -> Story:
    """A story on approved evidence, parked at a given editorial state."""
    evidence = overrides.pop("evidence", None) or approved_evidence(db, organisation)
    return make_story(db, evidence, status=status, **overrides)


def reload(db: Session, story: Story) -> Story:
    """Re-read a story after the API changed it."""
    db.expire_all()
    fresh = db.get(Story, story.id)
    assert fresh is not None
    return fresh


class TestSubmission:
    def test_a_draft_can_be_submitted_for_review(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.DRAFT)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(f"/api/v1/stories/{story.id}/submit", headers=auth_header(author))

        assert response.status_code == 200
        assert response.json()["status"] == "in_review"

    def test_a_rejected_story_can_be_resubmitted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.REJECTED)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(f"/api/v1/stories/{story.id}/submit", headers=auth_header(author))

        assert response.status_code == 200

    def test_a_published_story_cannot_be_resubmitted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.PUBLISHED)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(f"/api/v1/stories/{story.id}/submit", headers=auth_header(author))

        assert response.status_code == 409


class TestApprovalGate:
    def test_an_unapproved_story_cannot_be_published(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """The defect this replaces: publish was approval and publication at once."""
        story = story_at(db, organisation, S.IN_REVIEW)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/stories/{story.id}/publish", headers=auth_header(publisher)
        )

        assert response.status_code == 409
        assert reload(db, story).status is S.IN_REVIEW

    def test_the_author_cannot_approve_their_own_story(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        author = member(db, organisation, Role.EDITOR)
        story = story_at(db, organisation, S.IN_REVIEW, created_by=author.id)

        response = client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(author))

        assert response.status_code == 403

    def test_the_approver_cannot_also_publish(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Approval and release are two decisions; one person must not make both."""
        story = story_at(db, organisation, S.IN_REVIEW)
        editor = member(db, organisation, Role.EDITOR)

        approved = client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(editor))
        assert approved.status_code == 200

        response = client.post(f"/api/v1/stories/{story.id}/publish", headers=auth_header(editor))

        assert response.status_code == 403
        assert reload(db, story).status is S.APPROVED

    def test_approval_requires_an_approver_role(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.IN_REVIEW)
        translator = member(db, organisation, Role.TRANSLATOR)

        response = client.post(
            f"/api/v1/stories/{story.id}/approve", headers=auth_header(translator)
        )

        assert response.status_code == 403

    def test_only_a_story_under_review_can_be_approved(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.DRAFT)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(approver))

        assert response.status_code == 409

    def test_evidence_withdrawn_after_approval_blocks_publication(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Approval is not a licence to publish something that lost its basis."""
        evidence = approved_evidence(db, organisation)
        story = story_at(db, organisation, S.IN_REVIEW, evidence=evidence)
        approver = member(db, organisation, Role.APPROVER)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(approver))

        evidence.status = EvidenceStatus.ARCHIVED
        db.commit()

        response = client.post(
            f"/api/v1/stories/{story.id}/publish", headers=auth_header(publisher)
        )

        assert response.status_code == 409


class TestApprovalTrail:
    def test_an_approval_is_recorded_against_the_story(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.IN_REVIEW)
        approver = member(db, organisation, Role.APPROVER)

        client.post(
            f"/api/v1/stories/{story.id}/approve",
            json={"comments": "Reads well and the figures check out."},
            headers=auth_header(approver),
        )

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == story.id).one()
        assert record.entity_type == "story"
        assert record.decision.value == "approved"
        assert record.reviewer_id == approver.id
        assert record.comments == "Reads well and the figures check out."

    def test_a_rejection_is_recorded_with_its_reason(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.IN_REVIEW)
        approver = member(db, organisation, Role.APPROVER)

        response = client.post(
            f"/api/v1/stories/{story.id}/reject",
            json={"comments": "The second paragraph overstates the evidence."},
            headers=auth_header(approver),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        record = db.query(ApprovalRecord).filter(ApprovalRecord.entity_id == story.id).one()
        assert record.comments == "The second paragraph overstates the evidence."

    def test_rejecting_an_approved_story_clears_the_approval(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """An overturned approval must not stay on the record."""
        story = story_at(db, organisation, S.IN_REVIEW)
        approver = member(db, organisation, Role.APPROVER)

        client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(approver))
        client.post(
            f"/api/v1/stories/{story.id}/reject",
            json={"comments": "Compliance raised an objection."},
            headers=auth_header(approver),
        )

        fresh = reload(db, story)
        assert fresh.status is S.REJECTED
        assert fresh.approved_by is None
        assert fresh.approved_date is None

    def test_the_trail_returns_every_round_oldest_first(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.IN_REVIEW)
        approver = member(db, organisation, Role.APPROVER)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(
            f"/api/v1/stories/{story.id}/reject",
            json={"comments": "Needs a source line.", "changes_requested": True},
            headers=auth_header(approver),
        )
        client.post(f"/api/v1/stories/{story.id}/submit", headers=auth_header(author))
        client.post(
            f"/api/v1/stories/{story.id}/approve",
            json={"comments": "Source line added."},
            headers=auth_header(approver),
        )

        response = client.get(
            f"/api/v1/stories/{story.id}/approvals", headers=auth_header(approver)
        )

        assert response.status_code == 200
        assert [entry["decision"] for entry in response.json()] == [
            "changes_requested",
            "approved",
        ]

    def test_the_trail_is_not_readable_from_another_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        other = make_organisation(db)
        story = story_at(db, other, S.IN_REVIEW)
        outsider = member(db, organisation, Role.APPROVER)

        response = client.get(
            f"/api/v1/stories/{story.id}/approvals", headers=auth_header(outsider)
        )

        assert response.status_code == 404


class TestEditInvalidatesApproval:
    def test_editing_raises_the_version(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.DRAFT)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.put(
            f"/api/v1/stories/{story.id}",
            json={"body": "Revised body."},
            headers=auth_header(author),
        )

        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_editing_an_approved_story_sends_it_back_to_draft(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Otherwise an approval would cover words the approver never read."""
        story = story_at(db, organisation, S.IN_REVIEW)
        approver = member(db, organisation, Role.APPROVER)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(approver))
        client.put(
            f"/api/v1/stories/{story.id}",
            json={"body": "Quietly different body."},
            headers=auth_header(author),
        )

        fresh = reload(db, story)
        assert fresh.status is S.DRAFT
        assert fresh.approved_by is None

    def test_an_edited_story_cannot_be_published_on_its_old_approval(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.IN_REVIEW)
        approver = member(db, organisation, Role.APPROVER)
        author = member(db, organisation, Role.CONTENT_MANAGER)
        publisher = member(db, organisation, Role.EDITOR)

        client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(approver))
        client.put(
            f"/api/v1/stories/{story.id}",
            json={"body": "Rewritten after sign-off."},
            headers=auth_header(author),
        )

        response = client.post(
            f"/api/v1/stories/{story.id}/publish", headers=auth_header(publisher)
        )

        assert response.status_code == 409

    def test_a_published_story_cannot_be_edited(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.PUBLISHED)
        author = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.put(
            f"/api/v1/stories/{story.id}",
            json={"body": "Changed after the fact."},
            headers=auth_header(author),
        )

        assert response.status_code == 409
        assert reload(db, story).status is S.PUBLISHED


class TestWithdrawal:
    def test_a_published_story_can_be_withdrawn(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.PUBLISHED, featured=True)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/stories/{story.id}/withdraw",
            json={"reason": "The underlying figures were restated."},
            headers=auth_header(publisher),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "archived"

    def test_withdrawing_removes_it_from_the_featured_set(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """A retracted story must not keep running on the front page."""
        story = story_at(db, organisation, S.PUBLISHED, featured=True)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(
            f"/api/v1/stories/{story.id}/withdraw",
            json={"reason": "Retracted."},
            headers=auth_header(publisher),
        )

        assert reload(db, story).featured is False

    def test_withdrawal_requires_a_reason(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.PUBLISHED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/stories/{story.id}/withdraw",
            json={},
            headers=auth_header(publisher),
        )

        assert response.status_code == 422

    def test_a_published_story_cannot_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Deleting it would leave no trace that it was ever public."""
        story = story_at(db, organisation, S.PUBLISHED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.delete(f"/api/v1/stories/{story.id}", headers=auth_header(publisher))

        assert response.status_code == 409
        assert reload(db, story) is not None

    def test_a_draft_can_still_be_deleted(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.DRAFT)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.delete(f"/api/v1/stories/{story.id}", headers=auth_header(publisher))

        assert response.status_code == 200
        db.expire_all()
        assert db.get(Story, story.id) is None


class TestFeaturing:
    def test_only_a_published_story_can_be_featured(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.APPROVED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        response = client.post(
            f"/api/v1/stories/{story.id}/feature", headers=auth_header(publisher)
        )

        assert response.status_code == 409


class TestAuditTrail:
    def test_every_transition_is_recorded(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Stories previously wrote no audit entries at all."""
        story = story_at(db, organisation, S.DRAFT)
        author = member(db, organisation, Role.CONTENT_MANAGER)
        approver = member(db, organisation, Role.APPROVER)
        publisher = member(db, organisation, Role.EDITOR)

        client.post(f"/api/v1/stories/{story.id}/submit", headers=auth_header(author))
        client.post(f"/api/v1/stories/{story.id}/approve", headers=auth_header(approver))
        client.post(f"/api/v1/stories/{story.id}/publish", headers=auth_header(publisher))
        client.post(
            f"/api/v1/stories/{story.id}/withdraw",
            json={"reason": "Restated."},
            headers=auth_header(publisher),
        )

        actions = [
            entry.action
            for entry in db.query(AuditLog)
            .filter(AuditLog.entity_id == story.id)
            .order_by(AuditLog.created_at)
            .all()
        ]

        assert actions == ["submitted", "approved", "published", "withdrawn"]

    def test_the_withdrawal_reason_is_kept(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        story = story_at(db, organisation, S.PUBLISHED)
        publisher = member(db, organisation, Role.CONTENT_MANAGER)

        client.post(
            f"/api/v1/stories/{story.id}/withdraw",
            json={"reason": "The source withdrew its figures."},
            headers=auth_header(publisher),
        )

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.entity_id == story.id, AuditLog.action == "withdrawn")
            .one()
        )
        assert entry.new_values["reason"] == "The source withdrew its figures."
        assert entry.old_values["status"] == "published"
