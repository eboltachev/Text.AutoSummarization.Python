from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    display_name: Optional[str] = Field(default=None, description="Display name")


class UserDeleteRequest(BaseModel):
    user_id: str = Field(..., description="Identifier of the user to delete")


class UserDeleteResponse(BaseModel):
    status: str = Field(default="deleted", description="Deletion status")


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    inserted_at: float


class UserListResponse(BaseModel):
    users: List[UserResponse] = Field(default_factory=list)
