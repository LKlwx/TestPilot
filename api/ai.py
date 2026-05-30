import uuid
from datetime import datetime
from flask import Blueprint, request, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from core.response import success, error
from core.schema import validate_request
from api.schemas import AIGenerateSchema, AIAnalyzeSchema, AISaveApiSchema, AISaveUiSchema
from service.ai_service import ai_service
from extensions import db
from models import AsyncTask
from celery_app import celery_app


ai_bp = Blueprint("ai", __name__)


def _submit_task(task_type: str, task_name: str, args: list, user_id: int):
    """提交异步任务并创建 AsyncTask 记录"""
    task_id = str(uuid.uuid4())
    task = AsyncTask(
        id=task_id,
        task_type=task_type,
        status="pending",
        creator_id=user_id,
        create_time=datetime.now(),
    )
    db.session.add(task)
    db.session.commit()
    celery_app.send_task(task_name, args=args, task_id=task_id)
    return task_id


@ai_bp.route("/generate/api/page")
def gen_api_page():
    return render_template("ai_generate_api.html")


@ai_bp.route("/generate/ui/page")
def gen_ui_page():
    return render_template("ai_generate_ui.html")


@ai_bp.route("/analyze/page")
def analyze_page():
    return render_template("ai_analyze_failure.html")


@ai_bp.route("/generate/api", methods=["POST"])
@jwt_required()
def gen_api():
    data = validate_request(AIGenerateSchema, request.json)
    uid = int(get_jwt_identity())
    task_id = _submit_task("ai_generate", "ai_generate_api", [data["scene"], uid], uid)
    return success({"task_id": task_id}, "任务已提交")


@ai_bp.route("/generate/ui", methods=["POST"])
@jwt_required()
def gen_ui():
    data = validate_request(AIGenerateSchema, request.json)
    uid = int(get_jwt_identity())
    task_id = _submit_task("ai_generate", "ai_generate_ui", [data["scene"], uid], uid)
    return success({"task_id": task_id}, "任务已提交")


@ai_bp.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    data = validate_request(AIAnalyzeSchema, request.json)
    uid = int(get_jwt_identity())
    task_id = _submit_task("ai_analyze", "ai_analyze", [data["log"], uid], uid)
    return success({"task_id": task_id}, "任务已提交")


@ai_bp.route("/task/<task_id>", methods=["GET"])
@jwt_required()
def get_task_status(task_id):
    from core.exception import AuthException
    task = AsyncTask.query.get(task_id)
    if not task:
        return error("任务不存在")
    uid = int(get_jwt_identity())
    if task.creator_id != uid:
        raise AuthException("无权访问该任务")
    return success({
        "task_id": task.id,
        "status": task.status,
        "result": task.result,
        "error_msg": task.error_msg,
        "create_time": task.create_time.isoformat() if task.create_time else None,
        "finish_time": task.finish_time.isoformat() if task.finish_time else None,
    })


@ai_bp.route("/save/api", methods=["POST"])
@jwt_required()
def save_api():
    data = validate_request(AISaveApiSchema, request.json)
    uid = int(get_jwt_identity())
    ai_service.save_api(data, uid)
    return success(msg="保存成功")


@ai_bp.route("/save/ui", methods=["POST"])
@jwt_required()
def save_ui():
    data = validate_request(AISaveUiSchema, request.json)
    uid = int(get_jwt_identity())
    ai_service.save_ui(data, uid)
    return success(msg="保存成功")


@ai_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    task_type = request.args.get("type", "analyze_failure")
    uid = int(get_jwt_identity())
    data = ai_service.get_history(task_type, uid)
    return success(data)
