from flask import request
from sqlalchemy.exc import SQLAlchemyError

from core.logger import get_logger
from extensions import db
from models import SysOperationLog

logger = get_logger(__name__)


def add_operation_log(user_id, username, operation, detail, ip=None):
    if ip is None:
        ip = request.remote_addr
    log = SysOperationLog(user_id=user_id, username=username, operation=operation, ip=ip, detail=detail)
    db.session.add(log)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.error("操作日志写入失败: operation=%s, user=%s", operation, username)
        raise
