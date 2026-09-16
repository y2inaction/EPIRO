"""Database configuration and session management."""

from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    poolclass=NullPool,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Enable PostGIS when connecting."""
    cursor = dbapi_conn.cursor()
    cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pgvector")
    cursor.close()
