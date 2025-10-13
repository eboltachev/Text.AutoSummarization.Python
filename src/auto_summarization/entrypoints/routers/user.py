from auto_summarization.entrypoints.schemas.user import (
    CreateUserRequest,
    CreateUserResponse,
    DeleteUserRequest,
    DeleteUserResponse,
    UserInfo,
    UsersResponse,
)
from fastapi import APIRouter, HTTPException
from auto_summarization.services.data.unit_of_work import UserUoW
from auto_summarization.services.handlers.user import create_new_user, delete_exist_user, get_user_list

router = APIRouter()


@router.get("/get_users", response_model=UsersResponse, status_code=200)
async def get_users() -> UsersResponse:
    try:
        users = [UserInfo(**user) for user in get_user_list(uow=UserUoW())]
        return UsersResponse(users=users)
    except Exception as error:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/create_user", response_model=CreateUserResponse, status_code=200)
async def create_user(request: CreateUserRequest) -> CreateUserResponse:
    try:
        status = create_new_user(user_id=request.user_id, temporary=request.temporary, uow=UserUoW())
        return CreateUserResponse(status=status)
    except Exception as error:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=500, detail=str(error))


@router.delete("/delete_user", response_model=DeleteUserResponse, status_code=200)
async def delete_user(request: DeleteUserRequest) -> DeleteUserResponse:
    try:
        status = delete_exist_user(request.user_id, UserUoW())
        return DeleteUserResponse(status=status)
    except Exception as error:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=500, detail=str(error))
