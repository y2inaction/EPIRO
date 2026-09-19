"""Base repository class for common CRUD operations."""

from typing import Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.base import TimestampedModel

T = TypeVar("T", bound=TimestampedModel)

# Never assignable through a generic update, whatever a caller supplies.
IMMUTABLE_FIELDS = frozenset({"id", "created_at", "created_by", "updated_at"})


class BaseRepository(Generic[T]):
    """Base repository for CRUD operations."""

    def __init__(self, db: Session, model: Type[T]):
        """Initialize repository."""
        self.db = db
        self.model = model
        self._columns = frozenset(model.__table__.columns.keys())

    def create(self, obj_in: dict) -> T:
        """Create a new record."""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, id: UUID) -> Optional[T]:
        """Get a record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        desc_order: bool = False,
    ) -> tuple[List[T], int]:
        """Get all records with pagination."""
        query = self.db.query(self.model)
        total = query.count()

        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            if desc_order:
                query = query.order_by(desc(order_field))
            else:
                query = query.order_by(order_field)

        records = query.offset(skip).limit(limit).all()
        return records, total

    def update(self, id: UUID, obj_in: dict) -> Optional[T]:
        """Update a record from an already-validated field mapping.

        Callers pass a schema dump, not raw request data. Unknown keys are
        ignored and identity columns are never writable, so a field omitted
        from the update schema cannot be reached from a request body. Values
        of None are applied, which is what allows an optional field to be
        cleared.
        """
        db_obj = self.get_by_id(id)
        if not db_obj:
            return None

        for field, value in obj_in.items():
            if field in IMMUTABLE_FIELDS or field not in self._columns:
                continue
            setattr(db_obj, field, value)

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: UUID) -> bool:
        """Delete a record."""
        db_obj = self.get_by_id(id)
        if not db_obj:
            return False

        self.db.delete(db_obj)
        self.db.commit()
        return True

    def filter(self, **kwargs) -> List[T]:
        """Filter records by attributes."""
        query = self.db.query(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key) and value is not None:
                query = query.filter(getattr(self.model, key) == value)
        return query.all()

    def exists(self, **kwargs) -> bool:
        """Check if a record exists."""
        query = self.db.query(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key) and value is not None:
                query = query.filter(getattr(self.model, key) == value)
        return query.first() is not None
