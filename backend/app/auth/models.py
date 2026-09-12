"""Pydantic schemas for authentication and user administration.

No schema here ever contains a password hash or a plaintext password in any
serialized form (the hash is only ever consumed server-side and the password
only ever accepted on create/change).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str
    title: str
    is_active: bool
    is_demo: bool
    last_active_at: Optional[str] = None
    created_at: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str = Field(..., min_length=1, max_length=128)
    email: str = Field("", max_length=254)
    role: str = Field(..., min_length=1, max_length=32)
    title: str = Field("", max_length=128)
    password: str = Field(..., min_length=12, max_length=200)


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=128)
    email: Optional[str] = Field(None, max_length=254)
    role: Optional[str] = Field(None, min_length=1, max_length=32)
    title: Optional[str] = Field(None, max_length=128)
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=12, max_length=200)


class RoleOut(BaseModel):
    role: str
    permissions: List[str]


class UserListResponse(BaseModel):
    users: List[UserOut]
    source: str


class DemoSeedNotice(BaseModel):
    detail: str


TokenResponse.model_rebuild()