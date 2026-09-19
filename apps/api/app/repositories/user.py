"""User repository."""

import uuid
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User repository for database operations."""

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, User)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()

    def get_active_users(self, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
        """Get all active users."""
        query = self.db.query(User).filter(User.is_active.is_(True))
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        return users, total

    def search_users(
        self, query_str: str, skip: int = 0, limit: int = 100
    ) -> tuple[list[User], int]:
        """Search users by email, first name, or last name."""
        query = self.db.query(User).filter(
            or_(
                User.email.ilike(f"%{query_str}%"),
                User.first_name.ilike(f"%{query_str}%"),
                User.last_name.ilike(f"%{query_str}%"),
            )
        )
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        return users, total

    def deactivate_user(self, user_id: uuid.UUID) -> Optional[User]:
        """Deactivate a user."""
        user = self.get_by_id(user_id)
        if user:
            user.is_active = False
            self.db.commit()
            self.db.refresh(user)
        return user

    def activate_user(self, user_id: uuid.UUID) -> Optional[User]:
        """Activate a user."""
        user = self.get_by_id(user_id)
        if user:
            user.is_active = True
            self.db.commit()
            self.db.refresh(user)
        return user
