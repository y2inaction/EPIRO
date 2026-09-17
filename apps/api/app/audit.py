"""Audit trail recording.

The AuditLog model existed from the start but nothing ever wrote to it, so the
platform's accountability guarantee was unbacked. Every state change that a
reviewer might later need to account for goes through here.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User

# Action names are stable identifiers, not prose: they are queried and
# reported on, so they must not drift with wording changes.
LOGIN = "auth.login"
REGISTER = "auth.register"
PASSWORD_CHANGED = "auth.password_changed"

CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"
SUBMITTED = "submitted"
VERIFIED = "verified"
APPROVED = "approved"
REJECTED = "rejected"
PUBLISHED = "published"
WITHDRAWN = "withdrawn"
FEATURED = "featured"
DEACTIVATED = "user.deactivated"
ACTIVATED = "user.activated"


def serialise(value: Any) -> Any:
    """Coerce a model value into something JSONB can store."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (uuid.UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [serialise(item) for item in value]
    if isinstance(value, dict):
        return {key: serialise(item) for key, item in value.items()}
    return value


def _client_ip(request: Optional[Request]) -> Optional[str]:
    """Best-effort client address."""
    if request is None or request.client is None:
        return None
    return request.client.host


def _user_agent(request: Optional[Request]) -> Optional[str]:
    """Client user agent, truncated to the column width."""
    if request is None:
        return None
    agent = request.headers.get("user-agent")
    return agent[:500] if agent else None


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    user: Optional[User] = None,
    organisation_id: Optional[uuid.UUID] = None,
    evidence_id: Optional[uuid.UUID] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """Append an entry to the audit trail.

    Committed separately from the change it describes, because the
    repositories commit their own work. An audit write that fails therefore
    raises rather than passing silently: an unrecorded state change is the
    thing this module exists to prevent.
    """
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user.id if user is not None else None,
        organisation_id=organisation_id,
        evidence_id=evidence_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
