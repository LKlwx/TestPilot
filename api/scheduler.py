from flask import Blueprint, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from core.db_guard import db_write_guard
from core.exception import APIException, NotFoundException
from core.response import success
from extensions import db
from models import TestCase, TestTask, User
from service.operation_log_service import add_operation_log

scheduler_bp = Blueprint("scheduler", __name__)


@scheduler_bp.route("/page")
def scheduler_page():
    return render_template("scheduler.html")


@scheduler_bp.route("/tasks", methods=["GET"])
@jwt_required()
def get_tasks():
    tasks = TestTask.query.order_by(TestTask.id.desc()).all()
    suite_names = {}
    for t in tasks:
        if t.suite_id:
            from models import TestSuite

            s = TestSuite.query.get(t.suite_id)
            if s:
                suite_names[t.id] = s.name
    return success(
        {
            "list": [
                {
                    "id": t.id,
                    "name": t.name,
                    "cron_expr": t.cron_expr,
                    "status": t.status,
                    "case_count": t.cases.count(),
                    "last_run_time": t.last_run_time.strftime("%Y-%m-%d %H:%M") if t.last_run_time else None,
                    "last_status": t.last_status or "",
                    "suite_id": t.suite_id,
                    "suite_name": suite_names.get(t.id, ""),
                }
                for t in tasks
            ],
        }
    )


@scheduler_bp.route("/task/add", methods=["POST"])
@jwt_required()
def add_task():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("cron_expr"):
        raise APIException("名称和 Cron 表达式不能为空")
    _validate_cron(data["cron_expr"])

    case_ids = data.get("case_ids", [])
    suite_id = data.get("suite_id")
    task = TestTask(
        name=data["name"],
        cron_expr=data["cron_expr"].strip(),
        status="enabled",
        creator_id=int(get_jwt_identity()),
        suite_id=suite_id,
    )
    with db_write_guard("定时任务添加失败"):
        db.session.add(task)
        db.session.flush()
        if case_ids:
            cases = TestCase.query.filter(TestCase.id.in_(case_ids)).all()
            task.cases = cases
    return success(data={"id": task.id}, msg="定时任务创建成功")


@scheduler_bp.route("/task/<int:tid>", methods=["PUT"])
@jwt_required()
def update_task(tid):
    task = TestTask.query.get(tid)
    if not task:
        raise NotFoundException("定时任务不存在")
    data = request.get_json()
    if "cron_expr" in data:
        _validate_cron(data["cron_expr"])
        task.cron_expr = data["cron_expr"].strip()
    if "name" in data:
        if not data["name"]:
            raise APIException("任务名称不能为空")
        task.name = data["name"]
    if "case_ids" in data:
        ids = data["case_ids"]
        if not isinstance(ids, list):
            raise APIException("case_ids 应为数组")
        cases = TestCase.query.filter(TestCase.id.in_(ids)).all()
        task.cases = cases
    if "suite_id" in data:
        task.suite_id = data["suite_id"]
    with db_write_guard("定时任务更新失败"):
        db.session.flush()
    return success(msg="更新成功")


@scheduler_bp.route("/task/<int:tid>/toggle", methods=["POST"])
@jwt_required()
def toggle_task(tid):
    task = TestTask.query.get(tid)
    if not task:
        raise NotFoundException("定时任务不存在")
    task.status = "disabled" if task.status == "enabled" else "enabled"
    db.session.commit()
    return success(msg=f"定时任务已{'启用' if task.status == 'enabled' else '禁用'}")


@scheduler_bp.route("/task/<int:tid>", methods=["DELETE"])
@jwt_required()
def delete_task(tid):
    task = TestTask.query.get(tid)
    if not task:
        raise NotFoundException("定时任务不存在")
    task.cases = []  # 清空关联，避免外键约束
    db.session.flush()
    db.session.delete(task)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return success(msg="删除成功")


def _validate_cron(expr):
    """验证 Cron 表达式合法性"""
    try:
        from croniter import croniter
    except ImportError:
        import logging

        logging.getLogger(__name__).warning("croniter not installed; cron validation skipped")
        return
    if not croniter.is_valid(expr.strip()):
        raise APIException(f"Cron 表达式格式错误: {expr}")
