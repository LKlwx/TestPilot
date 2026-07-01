from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError

from core.exception import APIException
from core.logger import log_error
from extensions import db


@contextmanager
def db_write_guard(context=""):
    """DB 写入保护上下文管理器，统一异常回滚与日志记录"""
    try:
        yield
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        log_error(e, context=context)
        raise APIException("数据写入失败")
