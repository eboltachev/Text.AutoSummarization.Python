from typing import Optional

from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    user_id: str
    temporary: Optional[bool] = False


class CreateUserResponse(BaseModel):
    status: str


class DeleteUserRequest(BaseModel):
    user_id: str


class DeleteUserResponse(BaseModel):
    status: str


class UserInfo(BaseModel):
    user_id: str
    temporary: bool
    started_using_at: float
    last_used_at: float


class UsersResponse(BaseModel):
    users: list[UserInfo]
