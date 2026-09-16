"""User management endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_users():
    """List all users."""
    return {"users": []}


@router.get("/{user_id}")
async def get_user(user_id: str):
    """Get user by ID."""
    return {"user_id": user_id}


@router.post("/")
async def create_user():
    """Create a new user."""
    return {"message": "User created"}


@router.put("/{user_id}")
async def update_user(user_id: str):
    """Update user."""
    return {"user_id": user_id, "message": "User updated"}


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    """Delete user."""
    return {"user_id": user_id, "message": "User deleted"}
