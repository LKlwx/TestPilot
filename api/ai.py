from flask import Blueprint, request, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from core.response import success, error
from service.ai_service import ai_service

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/generate/api/page")
def gen_api_page():
    """接口用例生成页面"""
    return render_template("ai_generate_api.html")


@ai_bp.route("/generate/ui/page")
def gen_ui_page():
    """UI 用例生成页面"""
    return render_template("ai_generate_ui.html")


@ai_bp.route("/analyze/page")
def analyze_page():
    """测试失败分析页面"""
    return render_template("ai_analyze_failure.html")


@ai_bp.route("/generate/api", methods=["POST"])
@jwt_required()
def gen_api():
    """调用 AI 生成接口测试用例"""
    scene = request.json.get("scene", "").strip()
    if not scene: return error("场景不能为空")
    try:
        uid = get_jwt_identity()
        data = ai_service.generate_api(scene, int(uid))
        return success(data)
    except Exception as e:
        return error(f"AI生成失败：{str(e)}")


@ai_bp.route("/generate/ui", methods=["POST"])
@jwt_required()
def gen_ui():
    """调用 AI 生成 UI 测试用例"""
    scene = request.json.get("scene", "").strip()
    if not scene: return error("场景不能为空")
    try:
        uid = get_jwt_identity()
        data = ai_service.generate_ui(scene, int(uid))
        return success(data)
    except Exception as e:
        return error(f"AI生成失败：{str(e)}")


@ai_bp.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    """调用 AI 分析失败日志"""
    log = request.json.get("log", "").strip()
    if not log: return error("日志不能为空")
    try:
        uid = get_jwt_identity()
        res = ai_service.analyze_log(log, int(uid))
        return success({"result": res})
    except Exception as e:
        return error(f"AI分析失败：{str(e)}")


@ai_bp.route("/save/api", methods=["POST"])
@jwt_required()
def save_api():
    """保存 AI 生成的接口用例"""
    data = request.json
    uid = get_jwt_identity()
    ai_service.save_api(data, int(uid))
    return success(msg="保存成功")


@ai_bp.route("/save/ui", methods=["POST"])
@jwt_required()
def save_ui():
    """保存 AI 生成的 UI 用例"""
    data = request.json
    uid = get_jwt_identity()
    ai_service.save_ui(data, int(uid))
    return success(msg="保存成功")


@ai_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    """查询 AI 任务历史（支持按类型筛选）"""
    task_type = request.args.get("type", "analyze_failure")
    uid = get_jwt_identity()
    data = ai_service.get_history(task_type, int(uid))
    return success(data)
