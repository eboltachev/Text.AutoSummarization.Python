from entrypoints.schemas.user import (
    CreateUserRequest,
    CreateUserResponse,
    DeleteUserRequest,
    DeleteUserResponse,
    UserInfo,
    UsersResponse,
)
from fastapi import APIRouter
from services.data.unit_of_work import UserUoW
from services.handlers.user import create_new_user, delete_exist_user, get_user_list

router = APIRouter()


@router.get("/get_users", response_model=UsersResponse, status_code=200)
async def get_users() -> UsersResponse:
    try:
        users = [UserInfo(**user) for user in get_user_list(uow=UserUoW())]
        return UsersResponse(users=users)
    except Exception as error:
        raise HTTPException(status_code=404, detail=error)


@router.post("/create_user", response_model=CreateUserResponse, status_code=200)
async def create_user(request: CreateUserRequest) -> CreateUserResponse:
    try:
        uow = UserUoW()
        status = create_new_user(user_id=request.user_id, temporary=request.temporary, uow=uow)
        return CreateUserResponse(status=status)
    except Exception as error:
        raise HTTPException(status_code=404, detail=error)


@router.delete("/delete_user", response_model=DeleteUserResponse, status_code=200)
async def delete_user(request: DeleteUserRequest) -> DeleteUserResponse:
    try:
        uow = UserUoW()
        status = delete_exist_user(request.user_id, uow)
        return DeleteUserResponse(status=status)
    except Exception as error:
        raise HTTPException(status_code=404, detail=error)
