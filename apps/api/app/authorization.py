"""Organisation-scoped role checks.

Authorisation in EPIRO is always answered against a specific organisation.
A user holds a role per organisation through the ``user_organisation``
association, and every check asks "what may this user do *in this
organisation*" rather than "is this user an admin".
"""

import uuid
from typing import Dict, Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Role, User, user_organisation

# Role groups, named for the operation they authorise rather than for a
# hierarchy, so a reader can see what each endpoint actually requires.
EVIDENCE_AUTHORS = frozenset(
    {Role.RESEARCHER, Role.FIELD_OFFICER, Role.EVIDENCE_MANAGER, Role.EDITOR}
)
EVIDENCE_VERIFIERS = frozenset({Role.VERIFIER, Role.EVIDENCE_MANAGER})
EVIDENCE_MANAGERS = frozenset({Role.EVIDENCE_MANAGER})
APPROVERS = frozenset({Role.APPROVER, Role.EXECUTIVE})
ORG_ADMINS = frozenset({Role.EXECUTIVE})
# Lifecycle decisions about a programme or project: who may declare one
# complete, suspended or archived.
PROGRAMME_MANAGERS = frozenset({Role.EVIDENCE_MANAGER, Role.EXECUTIVE})
# Day-to-day recording against a project, including field staff reporting
# progress they observed.
PROJECT_EDITORS = frozenset(
    {Role.EVIDENCE_MANAGER, Role.EXECUTIVE, Role.RESEARCHER, Role.FIELD_OFFICER}
)
PUBLISHERS = frozenset({Role.CONTENT_MANAGER, Role.EDITOR})
CONTENT_AUTHORS = frozenset({Role.CONTENT_MANAGER, Role.EDITOR, Role.TRANSLATOR})
QUESTION_RESPONDERS = frozenset(
    {Role.RESEARCHER, Role.CONTENT_MANAGER, Role.EDITOR, Role.EVIDENCE_MANAGER}
)


class AccessControl:
    """Answers authorisation questions for one authenticated user."""

    def __init__(self, db: Session, user: User):
        """Initialise for the given user."""
        self.db = db
        self.user = user
        self._roles: Optional[Dict[uuid.UUID, Role]] = None

    @property
    def roles(self) -> Dict[uuid.UUID, Role]:
        """Map of organisation id to the user's role there, loaded once."""
        if self._roles is None:
            rows = self.db.execute(
                select(
                    user_organisation.c.organisation_id,
                    user_organisation.c.role,
                ).where(user_organisation.c.user_id == self.user.id)
            ).all()
            self._roles = {row.organisation_id: Role(row.role) for row in rows}
        return self._roles

    @property
    def organisation_ids(self) -> Set[uuid.UUID]:
        """Every organisation the user belongs to."""
        return set(self.roles)

    @property
    def is_platform_admin(self) -> bool:
        """True for platform-level administrators.

        Deliberately not "holds SUPER_ADMIN somewhere": that would let an
        administrator of one small tenant read every other tenant's data.
        SUPER_ADMIN is an organisation role; this flag is the platform one.
        """
        return bool(self.user.is_superuser)

    def role_in(self, organisation_id: uuid.UUID) -> Optional[Role]:
        """The user's role in one organisation, if any."""
        return self.roles.get(organisation_id)

    def can_access(self, organisation_id: Optional[uuid.UUID]) -> bool:
        """True if the caller may see data belonging to an organisation."""
        if self.is_platform_admin:
            return True
        return organisation_id is not None and organisation_id in self.roles

    def require_platform_admin(self) -> None:
        """Require platform-level administration rights."""
        if not self.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform administrator access required",
            )

    def require_member(self, organisation_id: uuid.UUID) -> None:
        """Require membership of an organisation."""
        if self.is_platform_admin:
            return
        if organisation_id not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organisation",
            )

    def require_role(self, organisation_id: uuid.UUID, allowed: frozenset) -> None:
        """Require one of ``allowed`` roles within an organisation."""
        if self.is_platform_admin:
            return

        role = self.roles.get(organisation_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organisation",
            )
        # SUPER_ADMIN carries full rights, but only inside its own organisation.
        if role is Role.SUPER_ADMIN:
            return
        if role not in allowed:
            permitted = ", ".join(sorted(member.value for member in allowed))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of: {permitted}",
            )

    def require_distinct_actor(self, previous_actor_id: Optional[uuid.UUID]) -> None:
        """Enforce separation of duties on a two-step workflow.

        A super admin is not exempt: the point of the check is that two people
        looked at the record, and bypassing it would defeat it entirely.
        """
        if previous_actor_id is not None and previous_actor_id == self.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Separation of duties: this step must be carried out by a "
                    "different person from the previous one"
                ),
            )


async def get_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccessControl:
    """Provide an AccessControl for the authenticated user."""
    return AccessControl(db, current_user)
