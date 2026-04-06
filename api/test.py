from flask import Blueprint, request
from core.response import success, error
from models import TestCase, TestReport
from extensions import db
from service.test_service import execute_test_case
from flask import render_template

test_bp = Blueprint("test", __name__)


@test_bp.route("/cases", methods=["GET"])
def get_cases():
    module = request.args.get("module", "")
    query = TestCase.query
    if module:
        query = query.filter_by(module=module)

    cases = query.all()
    data = [{
        "id": c.id,
        "name": c.name,
        "module": c.module,
        "method": c.method,
        "url": c.url,
        "headers": c.headers,
        "body": c.body,
        "expect": c.expect
    } for c in cases]
    return success(data)


@test_bp.route("/case", methods=["POST"])
def add_case():
    d = request.get_json()
    case = TestCase(
        name=d["name"],
        module=d.get("module", "默认模块"),
        method=d["method"],
        url=d["url"],
        headers=d.get("headers", "{}"),
        body=d.get("body", "{}"),
        expect=d.get("expect"),
        extract_var=d.get("extract_var", ""),
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
    data = request.get_json()
    case.name = data.get("name", case.name)
    case.module = data.get("module", case.module)
    case.method = data.get("method", case.method)
    case.url = data.get("url", case.url)
    case.headers = data.get("headers", case.headers)
    case.body = data.get("body", case.body)
    case.expect = data.get("expect", case.expect)
    case.extract_var = data.get("extract_var", case.extract_var)
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


@test_bp.route("/case/<int:cid>", methods=["PUT"])
def update_case(cid):
    """编辑接口用例"""
    case = TestCase.query.get(cid)
    if not case:
        return error("用例不存在")

    data = request.get_json()

    # 更新字段
    case.name = data.get("name", case.name)
    case.module = data.get("module", case.module)
    case.method = data.get("method", case.method)
    case.url = data.get("url", case.url)
    case.headers = data.get("headers", case.headers)
    case.body = data.get("body", case.body)
    case.expect = data.get("expect", case.expect)
    case.extract_var = data.get("extract_var", case.extract_var)
    try:
        db.session.commit()
        return success(msg="更新成功")
    except Exception as e:
        db.session.rollback()
        return error(f"更新失败：{str(e)}")


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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from flask import current_app

    ids = request.json.get("ids", [])
    if not ids:
        return error("请选择用例")

    results = []
    # 获取当前应用实例
    app = current_app._get_current_object()

    def run_case_in_thread(cid):
        # 在线程内创建应用上下文
        with app.app_context():
            case = TestCase.query.get(cid)
            if case:
                return execute_test_case(case)
            return {"case_id": cid, "status": "ERROR", "error": "Case not found"}

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_id = {executor.submit(run_case_in_thread, cid): cid for cid in ids}

        for future in as_completed(future_to_id):
            cid = future_to_id[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as e:
                results.append({"case_id": cid, "status": "ERROR", "error": str(e)})

    return success(results, f"批量执行完成，共 {len(results)} 条结果")
