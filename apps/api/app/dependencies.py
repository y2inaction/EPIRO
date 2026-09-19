"""Dependency injection utilities."""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_token

security = HTTPBearer(auto_error=False)

_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers=_UNAUTHENTICATED_HEADERS,
        )

    payload = decode_token(credentials.credentials)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=_UNAUTHENTICATED_HEADERS,
        )

    # A refresh token has a much longer lifetime and is only valid at the
    # refresh endpoint; accepting one here would silently extend session
    # length to the refresh window.
    if payload.get("type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A refresh token cannot be used to authenticate a request",
            headers=_UNAUTHENTICATED_HEADERS,
        )

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers=_UNAUTHENTICATED_HEADERS,
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers=_UNAUTHENTICATED_HEADERS,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return user
