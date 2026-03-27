from flask import Blueprint, render_template, request, jsonify
from extensions import db
from models import UICase
from service.ui_service import run_ui_case
from core.response import success, error

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
def add_ui_case():
    data = request.json
    case = UICase(
        name=data.get("name"),
        url=data.get("url"),
        steps=data.get("steps", "")
    )
    # db.session.add(case)
    # db.session.commit()
    # return success(msg="成功")
    try:
        db.session.add(case)
        db.session.commit()
        print("保存成功，用例ID:", case.id)  # 打印成功信息
    except Exception as e:
        db.session.rollback()  # 回滚事务
        print("保存失败:", str(e))  # 打印错误原因
        return error("保存失败：" + str(e))
    return success(msg="成功")


@ui_bp.route("/cases", methods=["GET"])
def get_ui_cases():
    cases = UICase.query.all()
    return success([
        {"id": c.id, "name": c.name, "url": c.url, "loc_type": c.loc_type} for c in cases
    ])


@ui_bp.route("/case/<int:cid>/run", methods=["POST"])
def run_ui(cid):
    case = UICase.query.get(cid)
    if not case:
        return error("用例不存在")
    res = run_ui_case(case)
    return success(res)


@ui_bp.route("/case/<int:cid>", methods=["DELETE"])
def delete_ui_case(cid):
    case = UICase.query.get(cid)
    if case:
        db.session.delete(case)
        db.session.commit()
    return success(msg="删除成功")


@ui_bp.route("/reports/data", methods=["GET"])
def get_ui_reports():
    from models import UIReport
    reports = UIReport.query.order_by(UIReport.id.desc()).limit(20).all()
    return jsonify(code=200, data=[
        {
            "id": r.id,
            "case_name": r.case_name,
            "status": r.status,
            "time": r.cost_time,
            "msg": r.error_msg,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S")
        } for r in reports
    ])


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


# 升级 UICase 增加定位方式（简历亮点）
@ui_bp.route("/case/struct", methods=["POST"])
def add_struct_ui():
    data = request.json
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
        print("新结构用例保存成功，ID:", case.id)
    except Exception as e:
        db.session.rollback()
        print("新结构用例保存失败:", str(e))
        return error("保存失败：" + str(e))
    return success(msg="创建成功")
