from flask import request
from models import SysOperationLog
from extensions import db


def add_operation_log(user_id, username, operation, detail):
    log = SysOperationLog(
        user_id=user_id,
        username=username,
        operation=operation,
        ip=request.remote_addr,
        detail=detail
    )
    db.session.add(log)
    db.session.commit()
