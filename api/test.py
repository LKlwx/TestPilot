from flask import Blueprint, request
from core.response import success, error
from models import TestCase, TestReport
from extensions import db
from service.test_service import execute_test_case
from flask import render_template

test_bp = Blueprint("test", __name__)


@test_bp.route("/cases", methods=["GET"])
def get_cases():
    cases = TestCase.query.all()
    data = [{
        "id": c.id,
        "name": c.name,
        "method": c.method,
        "url": c.url,
        "expect": c.expect
    } for c in cases]
    return success(data)


@test_bp.route("/case", methods=["POST"])
def add_case():
    d = request.get_json()
    case = TestCase(
        name=d["name"],
        method=d["method"],
        url=d["url"],
        headers=d.get("headers", "{}"),
        body=d.get("body", "{}"),
        expect=d.get("expect"),
    )
    try:
        db.session.add(case)
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # 回滚事务
        print("保存失败:", str(e))  # 打印错误原因
        return error("保存失败：" + str(e))
    return success(msg="成功")


@test_bp.route("/case/<int:cid>/run", methods=["POST"])
def run_case(cid):
    case = TestCase.query.get(cid)
    if not case:
        return error("用例不存在")
    res = execute_test_case(case)
    return success(res)


@test_bp.route("/case/<int:cid>", methods=["DELETE"])
def delete_case(cid):
    case = TestCase.query.get(cid)
    if not case:
        return error("用例不存在")
    db.session.delete(case)
    db.session.commit()
    return success("删除成功")


@test_bp.route("/reports/data", methods=["GET"])
def reports():
    reports = TestReport.query.order_by(TestReport.id.desc()).limit(20).all()
    data = [{
        "id": r.id,
        "case_name": r.case_name,
        "status": r.status,
        "time": r.cost_time,
        "code": r.response_code,
        "msg": r.error_msg,
        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S")
    } for r in reports]
    return success(data)


@test_bp.route("/page")
def test_page():
    return render_template("api_test.html")


@test_bp.route("/list")
def test_list_page():
    return render_template("api_test_list.html")


@test_bp.route("/reports")
def report_page():
    return render_template("report.html")


# 获取报告详情
@test_bp.route("/report/<int:rid>", methods=["GET"])
def get_report_detail(rid):
    report = TestReport.query.get(rid)
    if not report:
        return error("报告不存在")
    data = {
        "id": report.id,
        "case_name": report.case_name,
        "status": report.status,
        "cost_time": report.cost_time,
        "response_code": report.response_code,
        "response_body": report.response_body,
        "error_msg": report.error_msg,
        "create_time": report.create_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return success(data)


# 批量执行
@test_bp.route("/batch/run", methods=["POST"])
def batch_run():
    ids = request.json.get("ids", [])
    if not ids: return error("请选择用例")
    res_list = []
    for cid in ids:
        case = TestCase.query.get(cid)
        if case:
            res = execute_test_case(case)
            res_list.append(res)
    return success(res_list, "批量执行完成")
