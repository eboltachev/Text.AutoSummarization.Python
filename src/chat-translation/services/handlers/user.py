import logging
import sys
from time import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from domain.user import User
from services.data.unit_of_work import IUoW

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def get_user_list(uow: IUoW) -> List[Optional[Dict[str, Any]]]:
    logger.info(f"start get_user_list")
    try:
        with uow:
            users = uow.users.list()
            users = [
                {
                    "user_id": user.user_id,
                    "temporary": user.temporary,
                    "started_using_at": user.started_using_at,
                    "last_used_at": user.last_used_at
                }
                for user in users
            ]
        logger.info(f"{users=}")
    except Exception as error:
        logger.error(f"{error=}")
        users = []
    finally:
        logger.info(f"finish get_user_list")
        return users


def create_new_user(user_id: str, temporary: bool, uow: IUoW) -> str | None:
    logger.info(f"start create_new_user")
    logger.info(f"{user_id=}")
    logger.info(f"{uow=}")
    try:
        with uow:
            user = uow.users.get(object_id=user_id)
            if user is None:
                now = time()
                user = User(
                    user_id=user_id,
                    temporary=temporary,
                    started_using_at=now,
                    last_used_at=now,
                    sessions=[],
                )
                uow.users.add(user)
                uow.commit()
                status = "created"
            else:
                status = "exist"
            logger.info(f"{status=}")
    except Exception as error:
        logger.error(f"{error=}")
        status = "error"
    finally:
        logger.info(f"finish create_new_user")
        return status

def delete_exist_user(user_id: str, uow: IUoW) -> str:
    logger.info(f"start delete_user")
    logger.info(f"{user_id=}")
    logger.info(f"{uow=}")
    try:
        with uow:
            user = uow.users.get(object_id=user_id)
            if user is None:
                return False
            uow.users.delete(user_id)
            uow.commit()
        status = "deteted"
    except Exception as error:
        logger.error(f"{error=}")
        status = "error"
    finally:
        logger.info(f"finish delete_user")
        return status
