from flask import Blueprint, render_template, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import UICase
from service.ui_service import run_ui_case
from core.response import success, error
from api.auth import add_operation_log

ui_bp = Blueprint("ui", __name__)


# 页面
@ui_bp.route("/page")
def ui_page():
    return render_template("ui_test.html")


@ui_bp.route("/reports")
def ui_reports_page():
    return render_template("ui_report.html")


# 接口
@ui_bp.route("/case", methods=["POST"])
@jwt_required()
def add_ui_case():
    from models import User
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    data = request.json
    if not data or not data.get("name") or not data.get("url"):
        return error("参数不完整!")
    case = UICase(
        name=data.get("name"),
        url=data.get("url"),
        steps=data.get("steps", ""),
        loc_type=data.get("loc_type", "xpath"),
        loc_value=data.get("loc_value", ""),
    )
    try:
        db.session.add(case)
        db.session.commit()
        add_operation_log(identity, username, "add_ui_case", f"新增UI用例: {data['name']}")
    except Exception as e:
        db.session.rollback()
        print(f"UI用例添加失败:{e}")
        return error("保存失败")
    return success(msg="成功")


@ui_bp.route("/cases", methods=["GET"])
def get_ui_cases():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    keyword = request.args.get("keyword", "", type=str)

    query = UICase.query
    if keyword:
        query = query.filter(UICase.name.like(f"%{keyword}%"))

    total = query.count()
    cases = query.order_by(UICase.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return success({
        "list": [{
            "id": c.id,
            "name": c.name,
            "url": c.url,
            "loc_type": c.loc_type,
            "steps": c.steps
        } for c in cases],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })


@ui_bp.route("/case/<int:cid>/run", methods=["POST"])
def run_ui(cid):
    case = UICase.query.get(cid)
    if not case:
        return error("用例不存在")
    res = run_ui_case(case)
    return success(res)


@ui_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_ui_case(cid):
    from models import User
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = UICase.query.get(cid)
    if case:
        case_name = case.name
        db.session.delete(case)
        db.session.commit()
        add_operation_log(user.id, username, "delete_ui_case", f"删除UI用例: {case_name} (ID={cid})")
    return success(msg="删除成功")


@ui_bp.route("/reports/data", methods=["GET"])
def get_ui_reports():
    from models import UIReport
    reports = UIReport.query.order_by(UIReport.id.desc()).limit(20).all()
    data = [{
        "id": r.id,
        "case_name": r.case_name,
        "status": r.status,
        "time": r.cost_time,
        "msg": r.error_msg,
        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S")
    } for r in reports]
    return success(data)


# 报告详情
@ui_bp.route("/report/<int:rid>", methods=["GET"])
def get_ui_report_detail(rid):
    from models import UIReport
    report = UIReport.query.get(rid)
    if not report:
        return error("报告不存在")

    data = {
        "id": report.id,
        "case_name": report.case_name,
        "status": report.status,
        "time": report.cost_time,
        "msg": report.error_msg,
        "create_time": report.create_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return success(data=data)


# 升级 UICase 增加定位方式
@ui_bp.route("/case/struct", methods=["POST"])
def add_struct_ui():
    data = request.json
    if not data or not data.get("name") or not data.get("url"):
        return error("参数不完整!")
    case = UICase(
        name=data["name"],
        url=data["url"],
        steps=data.get("steps", ""),
        loc_type=data.get("loc_type", "xpath"),
        loc_value=data.get("loc_value", ""),
        screenshot_path=data.get("screenshot_path", ""),
    )
    try:
        db.session.add(case)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"UI用例添加失败:{e}")
        return error("保存失败")
    return success(msg="创建成功")


# 编辑UI用例
@ui_bp.route("/case/<int:cid>", methods=["PUT"])
@jwt_required()
def update_ui_case(cid):
    from models import User
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = UICase.query.get(cid)
    if not case:
        return error("用例不存在")

    old_name = case.name
    data = request.json
    case.name = data.get("name", case.name)
    case.url = data.get("url", case.url)
    case.steps = data.get("steps", case.steps)
    case.loc_type = data.get("loc_type", case.loc_type)
    case.loc_value = data.get("loc_value", case.loc_value)

    try:
        db.session.commit()
        add_operation_log(user.id, username, "update_ui_case", f"修改UI用例: {old_name} → {case.name} (ID={cid})")
        return success(msg="更新成功")
    except Exception as e:
        db.session.rollback()
        return error(f"更新失败：{str(e)}")
