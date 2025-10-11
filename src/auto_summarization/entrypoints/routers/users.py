from __future__ import annotations

from fastapi import APIRouter, Depends

from auto_summarization.entrypoints.schemas.user import (
    UserCreateRequest,
    UserDeleteRequest,
    UserDeleteResponse,
    UserListResponse,
    UserResponse,
)
from auto_summarization.services.user_service import UserService


router = APIRouter()


def get_service() -> UserService:
    return UserService()


@router.get("/user/get_users", response_model=UserListResponse)
async def get_users(service: UserService = Depends(get_service)) -> UserListResponse:
    users = service.list_users()
    return UserListResponse(users=[UserResponse(**user) for user in users])


@router.post("/user/create_user", response_model=UserResponse)
async def create_user(
    payload: UserCreateRequest,
    service: UserService = Depends(get_service),
) -> UserResponse:
    user = service.create_user(payload.user_id, payload.display_name)
    return UserResponse(**user)


@router.delete("/user/delete_user", response_model=UserDeleteResponse)
async def delete_user(
    payload: UserDeleteRequest,
    service: UserService = Depends(get_service),
) -> UserDeleteResponse:
    service.delete_user(payload.user_id)
    return UserDeleteResponse()
