from __future__ import annotations

import logging
import sys
from time import time
from typing import Any, Dict, List

from auto_summarization.domain.user import User
from auto_summarization.services.data.unit_of_work import IUoW

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def get_user_list(uow: IUoW) -> List[Dict[str, Any]]:
    logger.info("start get_user_list")
    with uow:
        users = [
            {
                "user_id": user.user_id,
                "temporary": user.temporary,
                "started_using_at": user.started_using_at,
                "last_used_at": user.last_used_at,
            }
            for user in uow.users.list()
            if not user.temporary
        ]
    logger.info("finish get_user_list")
    return users


def create_new_user(user_id: str, temporary: bool, uow: IUoW) -> str:
    logger.info("start create_new_user")
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is not None:
            logger.info("user already exists")
            return "exist"
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
    logger.info("finish create_new_user")
    return "created"


def delete_exist_user(user_id: str, uow: IUoW) -> str:
    logger.info("start delete_user")
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            return "not_found"
        uow.users.delete(user_id)
        uow.commit()
    logger.info("finish delete_user")
    return "deleted"
