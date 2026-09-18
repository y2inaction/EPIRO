"""User management endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.authorization import AccessControl, get_access
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Organisation, User, user_organisation
from app.repositories.user import UserRepository
from app.schemas.auth import (
    CurrentUserResponse,
    OrganisationMembership,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


def _shares_an_organisation(db: Session, access: AccessControl, user_id: uuid.UUID) -> bool:
    """True if the target user belongs to any organisation the caller does."""
    if not access.organisation_ids:
        return False
    return (
        db.query(user_organisation)
        .filter(
            user_organisation.c.user_id == user_id,
            user_organisation.c.organisation_id.in_(access.organisation_ids),
        )
        .first()
        is not None
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The caller's own profile, with the memberships that decide what they may do.

    Roles are held per organisation, so a client cannot know which actions to
    offer until it knows which organisations the caller is in and with which
    role in each. Only the caller's own memberships are ever returned.
    """
    rows = (
        db.query(
            user_organisation.c.organisation_id,
            user_organisation.c.role,
            Organisation.name,
            Organisation.code,
        )
        .join(Organisation, Organisation.id == user_organisation.c.organisation_id)
        .filter(user_organisation.c.user_id == current_user.id)
        .order_by(Organisation.name)
        .all()
    )

    profile = CurrentUserResponse.model_validate(current_user)
    profile.memberships = [
        OrganisationMembership(
            organisation_id=row.organisation_id,
            name=row.name,
            code=row.code,
            role=row.role.value if hasattr(row.role, "value") else str(row.role),
        )
        for row in rows
    ]
    return profile


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user profile."""
    user_repo = UserRepository(db)
    update_data = user_update.model_dump(exclude_unset=True)

    updated_user = user_repo.update(current_user.id, update_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return updated_user


@router.get("/", response_model=dict)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """List all users (super administrators only)."""
    access.require_platform_admin()

    user_repo = UserRepository(db)
    if search:
        users, total = user_repo.search_users(search, skip, limit)
    else:
        users, total = user_repo.get_all(skip, limit)

    return {
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
        "data": [UserResponse.model_validate(user) for user in users],
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Get a user visible to the caller.

    Visible means the caller themselves, anyone sharing one of their
    organisations, or any user when the caller is a super admin.
    """
    if not (
        user_id == access.user.id
        or access.is_platform_admin
        or _shares_an_organisation(db, access, user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = UserRepository(db).get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Update a user profile (self, or a super administrator)."""
    if user_id != access.user.id and not access.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other users",
        )

    user_repo = UserRepository(db)
    if not user_repo.get_by_id(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_data = user_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = access.user.id

    return user_repo.update(user_id, update_data)


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Deactivate a user (super administrators only)."""
    access.require_platform_admin()

    if user_id == access.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    if not UserRepository(db).deactivate_user(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"message": "User deactivated successfully"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: uuid.UUID,
    access: AccessControl = Depends(get_access),
    db: Session = Depends(get_db),
):
    """Activate a user (super administrators only)."""
    access.require_platform_admin()

    if not UserRepository(db).activate_user(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"message": "User activated successfully"}
