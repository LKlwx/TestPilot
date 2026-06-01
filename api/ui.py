from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import UICase, User, UIReport
from service.ui_service import run_ui_case, parse_steps
from core.response import success, error
from core.pagination import paginate
from core.db_guard import db_write_guard
from core.schema import validate_request
from api.schemas import AddUICaseSchema, UpdateUICaseSchema, AddUIStructSchema
from service.operation_log_service import add_operation_log

ui_bp = Blueprint("ui", __name__)


# 页面
@ui_bp.route("/page")
def ui_page():
    return render_template("ui_test.html")


@ui_bp.route("/page/reports")
def ui_reports_page():
    return render_template("ui_report.html")


# 接口
@ui_bp.route("/case", methods=["POST"])
@jwt_required()
def add_ui_case():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    data = validate_request(AddUICaseSchema, request.json)

    steps = data.get("steps", "")
    if steps:
        is_valid, _, errors = parse_steps(steps)
        if not is_valid:
            error_msg = "步骤格式不符合规范：\n" + "\n".join(errors)
            return error(error_msg)

    case = UICase(
        name=data["name"],
        url=data["url"],
        steps=steps,
        loc_type=data.get("loc_type", "xpath"),
        loc_value=data.get("loc_value", ""),
        tags=data.get("tags", ""),
    )
    with db_write_guard("UI用例添加失败"):
        db.session.add(case)
        db.session.flush()
    cur = User.query.get(int(get_jwt_identity()))
    add_operation_log(cur.id, cur.username if cur else "未知", "add_ui_case", f"新增 UI 用例：{data['name']}")
    return success(data={"id": case.id}, msg="成功")


@ui_bp.route("/cases", methods=["GET"])
@jwt_required()
def get_ui_cases():
    keyword = request.args.get("keyword", "", type=str)
    tag = request.args.get("tag", "", type=str)

    query = UICase.query
    if keyword:
        query = query.filter(UICase.name.like(f"%{keyword}%"))
    if tag:
        query = query.filter(UICase.tags.like(f"%{tag.strip()}%"))

    result = paginate(query, order_by=UICase.id.desc())

    return success({
        "list": [{
            "id": c.id,
            "name": c.name,
            "url": c.url,
            "loc_type": c.loc_type,
            "steps": c.steps,
            "tags": c.tags,
        } for c in result.items],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


@ui_bp.route("/case/<int:cid>/run", methods=["POST"])
@jwt_required()
def run_ui(cid):
    case = UICase.query.get(cid)
    if not case:
        return error("用例不存在")
    res = run_ui_case(case)
    return success(res)


@ui_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_ui_case(cid):
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
@jwt_required()
def get_ui_reports():
    keyword = request.args.get("keyword", "", type=str)
    status = request.args.get("status", "", type=str)
    start_date = request.args.get("start_date", "", type=str)
    end_date = request.args.get("end_date", "", type=str)

    query = UIReport.query
    if keyword:
        query = query.filter(UIReport.case_name.like(f"%{keyword}%"))
    if status:
        query = query.filter(UIReport.status == status.upper())
    if start_date:
        query = query.filter(UIReport.create_time >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(UIReport.create_time < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))

    result = paginate(query, order_by=UIReport.id.desc(), page_size=20)
    return success({
        "list": [{
            "id": r.id, "case_name": r.case_name, "status": r.status,
            "time": r.cost_time, "msg": r.error_msg,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S")
        } for r in result.items],
        "total": result.total, "page": result.page,
        "page_size": result.page_size, "total_pages": result.total_pages,
    })


# 报告详情
@ui_bp.route("/report/<int:rid>", methods=["GET"])
@jwt_required()
def get_ui_report_detail(rid):
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
@jwt_required()
def add_struct_ui():
    data = validate_request(AddUIStructSchema, request.json)

    if data["steps"]:
        is_valid, _, errors = parse_steps(data["steps"])
        if not is_valid:
            error_msg = "步骤格式不符合规范：\n" + "\n".join(errors)
            return error(error_msg)

    case = UICase(
        name=data["name"],
        url=data["url"],
        steps=data["steps"],
        loc_type=data["loc_type"],
        loc_value=data["loc_value"],
        screenshot_path=data["screenshot_path"],
        tags=data["tags"],
    )
    with db_write_guard("UI用例添加失败"):
        db.session.add(case)
        db.session.flush()
    cur = User.query.get(int(get_jwt_identity()))
    add_operation_log(cur.id, cur.username if cur else "未知", "add_ui_case", f"新增 UI 用例：{data['name']}")
    return success(data={"id": case.id}, msg="创建成功")


# 编辑UI用例
@ui_bp.route("/case/<int:cid>", methods=["PUT"])
@jwt_required()
def update_ui_case(cid):
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = UICase.query.get(cid)
    if not case:
        return error("用例不存在")

    old_name = case.name
    old_url = case.url
    old_steps = case.steps
    old_loc_type = case.loc_type
    old_loc_value = case.loc_value
    data = validate_request(UpdateUICaseSchema, request.json)

    steps = data.get("steps", case.steps)
    if steps and steps != case.steps:
        is_valid, _, errors = parse_steps(steps)
        if not is_valid:
            error_msg = "步骤格式不符合规范：\n" + "\n".join(errors)
            return error(error_msg)

    # 记录修改的字段
    changes = []
    new_name = data.get("name", case.name)
    new_url = data.get("url", case.url)
    new_steps = data.get("steps", case.steps)
    new_loc_type = data.get("loc_type", case.loc_type)
    new_loc_value = data.get("loc_value", case.loc_value)

    if old_name != new_name:
        changes.append(f"名称({old_name}→{new_name})")
    if old_url != new_url:
        changes.append(f"URL({old_url[:20]}...→{new_url[:20]}...)")
    if old_steps != new_steps:
        changes.append(f"步骤({old_steps.split(chr(10)) if old_steps else []}→{new_steps.split(chr(10)) if new_steps else []})")
    if old_loc_type != new_loc_type:
        changes.append(f"定位方式({old_loc_type}→{new_loc_type})")
    if old_loc_value != new_loc_value:
        changes.append(f"定位值({old_loc_value}→{new_loc_value})")

    case.name = new_name
    case.url = new_url
    case.steps = new_steps
    case.loc_type = new_loc_type
    case.loc_value = new_loc_value
    case.tags = data.get("tags", case.tags)

    with db_write_guard("UI用例更新失败"):
        db.session.flush()
    detail = f"修改UI用例: {old_name} → {case.name}"
    if changes:
        detail += "，" + "，".join(changes)
    detail += f" (ID={cid})"
    add_operation_log(user.id, username, "update_ui_case", detail)
    return success(msg="更新成功")
