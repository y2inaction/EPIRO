"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "ok"}


@router.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe - checks database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}
