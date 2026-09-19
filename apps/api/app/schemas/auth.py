"""Authentication schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


class UserCreate(UserBase):
    """User creation schema."""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update schema."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class UserResponse(UserBase):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    is_verified: bool
    timezone: Optional[str] = None
    language: str
    created_at: datetime
    updated_at: datetime


class OrganisationMembership(BaseModel):
    """One organisation the caller belongs to, and their role in it."""

    organisation_id: uuid.UUID
    name: str
    code: str
    role: str


class CurrentUserResponse(UserResponse):
    """The caller's own profile, with the memberships that decide what they may do.

    A client cannot render an editorial workspace without this. Roles are held
    per organisation, so "what may I do" has no answer until you know which
    organisations the caller is in and with which role in each. Before this,
    nothing in the API told a signed-in caller either, and a client would have
    had to offer every action and let the server refuse most of them.
    """

    memberships: List[OrganisationMembership] = []


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
