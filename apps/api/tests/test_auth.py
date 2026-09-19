"""Authentication endpoint tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Organisation, Role
from app.security import create_access_token, verify_password
from tests.conftest import auth_header, grant_role, make_organisation, make_user, member

PASSWORD = "correct-horse-battery"


class TestRegistration:
    def test_registers_a_new_user(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newcomer@example.com",
                "first_name": "New",
                "last_name": "Comer",
                "password": PASSWORD,
            },
        )
        assert response.status_code == 200
        assert response.json()["email"] == "newcomer@example.com"

    def test_rejects_a_duplicate_email(self, client: TestClient, db: Session):
        existing = make_user(db)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": existing.email,
                "first_name": "Dup",
                "last_name": "Licate",
                "password": PASSWORD,
            },
        )
        assert response.status_code == 400

    def test_rejects_a_short_password(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "shorty@example.com",
                "first_name": "Short",
                "last_name": "Password",
                "password": "abc",
            },
        )
        assert response.status_code == 422

    def test_does_not_return_the_password_hash(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "discreet@example.com",
                "first_name": "Dis",
                "last_name": "Creet",
                "password": PASSWORD,
            },
        )
        assert "password_hash" not in response.json()
        assert "password" not in response.json()


class TestLogin:
    def test_returns_tokens_for_valid_credentials(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD)

        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert response.status_code == 200

        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user"]["email"] == user.email

    def test_rejects_a_wrong_password(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD)

        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "not-the-password"}
        )
        assert response.status_code == 401

    def test_rejects_an_unknown_email(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": PASSWORD},
        )
        assert response.status_code == 401

    def test_rejects_an_inactive_user(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD, is_active=False)

        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert response.status_code == 403


class TestRefresh:
    def test_issues_new_tokens_for_a_refresh_token(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD)
        login = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
        refresh_token = login.json()["refresh_token"]

        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_rejects_an_access_token(self, client: TestClient, db: Session):
        """An access token carries no refresh type and must not be accepted."""
        user = make_user(db)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": create_access_token(str(user.id))},
        )
        assert response.status_code == 401

    def test_rejects_a_malformed_token(self, client: TestClient):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert response.status_code == 401


class TestChangePassword:
    def test_changes_the_password(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD)

        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "a-brand-new-secret",
                "confirm_password": "a-brand-new-secret",
            },
            headers=auth_header(user),
        )
        assert response.status_code == 200

        db.refresh(user)
        assert verify_password("a-brand-new-secret", user.password_hash)

    def test_rejects_a_wrong_current_password(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD)

        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "wrong",
                "new_password": "a-brand-new-secret",
                "confirm_password": "a-brand-new-secret",
            },
            headers=auth_header(user),
        )
        assert response.status_code == 401

        db.refresh(user)
        assert verify_password(PASSWORD, user.password_hash)

    def test_rejects_a_mismatched_confirmation(self, client: TestClient, db: Session):
        user = make_user(db, password=PASSWORD)

        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "a-brand-new-secret",
                "confirm_password": "something-else-entirely",
            },
            headers=auth_header(user),
        )
        assert response.status_code == 400

    def test_requires_authentication(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "a-brand-new-secret",
                "confirm_password": "a-brand-new-secret",
            },
        )
        assert response.status_code == 401


class TestCurrentUserMemberships:
    """A client cannot render a workspace without knowing the caller's roles."""

    def test_me_reports_the_organisations_the_caller_belongs_to(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        user = member(db, organisation, Role.VERIFIER)

        response = client.get("/api/v1/users/me", headers=auth_header(user))

        assert response.status_code == 200
        memberships = response.json()["memberships"]
        assert len(memberships) == 1
        assert memberships[0]["organisation_id"] == str(organisation.id)
        assert memberships[0]["name"] == organisation.name
        assert memberships[0]["role"] == "verifier"

    def test_a_role_is_reported_per_organisation(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        """Roles are held per organisation, so the same person can differ."""
        other = make_organisation(db)
        user = member(db, organisation, Role.VERIFIER)
        grant_role(db, user, other, Role.APPROVER)

        response = client.get("/api/v1/users/me", headers=auth_header(user))

        roles = {m["organisation_id"]: m["role"] for m in response.json()["memberships"]}
        assert roles[str(organisation.id)] == "verifier"
        assert roles[str(other.id)] == "approver"

    def test_another_persons_memberships_are_never_included(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        member(db, organisation, Role.APPROVER)
        outsider = make_user(db)

        response = client.get("/api/v1/users/me", headers=auth_header(outsider))

        assert response.status_code == 200
        assert response.json()["memberships"] == []

    def test_the_password_hash_is_never_returned(
        self, client: TestClient, db: Session, organisation: Organisation
    ):
        user = member(db, organisation, Role.VERIFIER)

        body = client.get("/api/v1/users/me", headers=auth_header(user)).json()

        assert "password_hash" not in body
        assert "password" not in body
