from concurrent.futures import ThreadPoolExecutor,as_completed

from flask import Blueprint, request

from app import create_app
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
    data = request.get_json()
    if not data or not data.get("name") or not data.get("method") or not data.get("url"):
        return error("参数不完整!")
    case = TestCase(
        name=data["name"],
        method=data["method"],
        url=data["url"],
        headers=data.get("headers", "{}"),
        body=data.get("body", "{}"),
        expect=data.get("expect"),
    )
    try:
        db.session.add(case)
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # 回滚事务
        print(f"接口用例添加失败:{e}")  # 打印错误原因
        return error("保存失败")
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
    req = request.json
    if not req: return error("参数不完整!")
    ids = req.get("ids", [])
    if not ids: return error("请选择用例")
    res_list = []
    app = create_app()

    def run_single_case(cid):
        # 执行单个用例
        with app.app_context():
            case = TestCase.query.get(cid)
            if case:
                res = execute_test_case(case)
                return res
            return None

    with ThreadPoolExecutor(max_workers = 5) as executor:
        # 提交任务
        future_to_cid = {executor.submit(run_single_case, cid): cid for cid in ids}
        # 获取结果
        for future in as_completed(future_to_cid):
            try:
                res = future.result()
                if res:
                    res_list.append(res)
            except Exception as e:
                cid = future_to_cid[future]
                res_list.append({
                    "case_id" : cid,
                    "status" : "ERROR",
                    "msg" : str(e),
                })
    return success(res_list, "批量执行完成")
