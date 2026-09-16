"""Organisation management endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_organisations():
    """List all organisations."""
    return {"organisations": []}


@router.get("/{organisation_id}")
async def get_organisation(organisation_id: str):
    """Get organisation by ID."""
    return {"organisation_id": organisation_id}


@router.post("/")
async def create_organisation():
    """Create a new organisation."""
    return {"message": "Organisation created"}


@router.put("/{organisation_id}")
async def update_organisation(organisation_id: str):
    """Update organisation."""
    return {"organisation_id": organisation_id, "message": "Organisation updated"}


@router.delete("/{organisation_id}")
async def delete_organisation(organisation_id: str):
    """Delete organisation."""
    return {"organisation_id": organisation_id, "message": "Organisation deleted"}
