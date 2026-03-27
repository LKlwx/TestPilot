from flask import Blueprint, request, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from core.response import success, error
from service.ai_service import ai_service

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


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
    scene = request.json.get("scene", "").strip()
    if not scene: return error("场景不能为空")
    uid = get_jwt_identity()
    data = ai_service.generate_api(scene, int(uid))
    return success(data)


@ai_bp.route("/generate/ui", methods=["POST"])
@jwt_required()
def gen_ui():
    scene = request.json.get("scene", "").strip()
    if not scene: return error("场景不能为空")
    uid = get_jwt_identity()
    data = ai_service.generate_ui(scene, int(uid))
    return success(data)


@ai_bp.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    log = request.json.get("log", "").strip()
    if not log: return error("日志不能为空")
    uid = get_jwt_identity()
    res = ai_service.analyze_log(log, int(uid))
    return success({"result": res})


@ai_bp.route("/save/api", methods=["POST"])
@jwt_required()
def save_api():
    data = request.json
    uid = get_jwt_identity()
    ai_service.save_api(data, int(uid))
    return success(msg="保存成功")


@ai_bp.route("/save/ui", methods=["POST"])
@jwt_required()
def save_ui():
    data = request.json
    uid = get_jwt_identity()
    ai_service.save_ui(data, int(uid))
    return success(msg="保存成功")
