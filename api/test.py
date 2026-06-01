from flask import Blueprint, request, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity

from core.exception import NotFoundException
from core.response import success, error
from core.pagination import paginate
from core.db_guard import db_write_guard
from core.schema import validate_request
from api.schemas import AddTestCaseSchema, UpdateTestCaseSchema, BatchRunSchema
from models import TestCase, TestReport, AsyncTask, BatchTask, BatchResult, User
from extensions import db
from service.test_service import execute_test_case
from service.operation_log_service import add_operation_log
from celery_app import celery_app
from datetime import datetime, timedelta
from sqlalchemy import or_
import uuid

test_bp = Blueprint("test", __name__)


@test_bp.route("/cases", methods=["GET"])
@jwt_required()
def get_cases():
    keyword = request.args.get("keyword", "", type=str)
    tag = request.args.get("tag", "", type=str)

    query = TestCase.query
    if keyword:
        query = query.filter(TestCase.name.like(f"%{keyword}%"))
    if tag:
        query = query.filter(TestCase.tags.like(f"%{tag.strip()}%"))

    result = paginate(query, order_by=TestCase.id.desc())

    data = [{
        "id": c.id,
        "name": c.name,
        "module": c.module,
        "method": c.method,
        "url": c.url,
        "expect": c.expect,
        "timeout": c.timeout,
        "retry": c.retry,
        "tags": c.tags,
    } for c in result.items]

    return success({
        "list": data,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


@test_bp.route("/case", methods=["POST"])
@jwt_required()
def add_case():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    data = validate_request(AddTestCaseSchema, request.get_json())
    case = TestCase(
        name=data["name"],
        module=data.get("module"),
        method=data["method"],
        url=data["url"],
        headers=data.get("headers", "{}"),
        body=data.get("body", "{}"),
        expect=data.get("expect"),
        extract_var=data.get("extract_var"),
        timeout=data.get("timeout", 10),
        retry=data.get("retry", 0),
        tags=data.get("tags", ""),
    )
    with db_write_guard("接口用例添加失败"):
        db.session.add(case)
        db.session.flush()
    add_operation_log(user.id, username, "add_case", f"新增接口用例: {data['name']}")
    return success(data={"id": case.id}, msg="成功")


@test_bp.route("/case/<int:cid>/run", methods=["POST"])
@jwt_required()
def run_case(cid):
    case = TestCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    res = execute_test_case(case)
    return success(res)


@test_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_case(cid):
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = TestCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    case_name = case.name
    db.session.delete(case)
    db.session.commit()
    add_operation_log(user.id, username, "delete_case", f"删除接口用例: {case_name} (ID={cid})")
    return success("删除成功")


@test_bp.route("/case/<int:cid>", methods=["PUT"])
@jwt_required()
def update_case(cid):
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = TestCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    old_name = case.name
    old_module = case.module
    old_method = case.method
    old_url = case.url
    old_expect = case.expect
    old_extract_var = case.extract_var
    data = validate_request(UpdateTestCaseSchema, request.get_json())

    # 记录修改的字段
    changes = []
    new_name = data.get("name", case.name)
    new_module = data.get("module", case.module)
    new_method = data.get("method", case.method)
    new_url = data.get("url", case.url)
    new_expect = data.get("expect", case.expect)
    new_extract_var = data.get("extract_var", case.extract_var)

    if old_name != new_name:
        changes.append(f"名称({old_name}→{new_name})")
    if old_module != new_module:
        changes.append(f"模块({old_module}→{new_module})")
    if old_method != new_method:
        changes.append(f"方法({old_method}→{new_method})")
    if old_url != new_url:
        changes.append(f"URL({old_url[:30]}...→{new_url[:30]}...)")
    if old_expect != new_expect:
        changes.append(f"预期({old_expect}→{new_expect})")
    if old_extract_var != new_extract_var:
        changes.append(f"提取变量({old_extract_var}→{new_extract_var})")

    case.name = new_name
    case.module = new_module
    case.method = new_method
    case.url = new_url
    case.headers = data.get("headers", case.headers)
    case.body = data.get("body", case.body)
    case.expect = new_expect
    case.extract_var = new_extract_var
    case.timeout = data.get("timeout", case.timeout)
    case.retry = data.get("retry", case.retry)
    case.tags = data.get("tags", case.tags)

    db.session.commit()
    detail = f"修改接口用例: {old_name} → {case.name}"
    if changes:
        detail += "，" + "，".join(changes)
    detail += f" (ID={cid})"
    add_operation_log(user.id, username, "update_case", detail)
    return success(msg="更新成功")


@test_bp.route("/reports/data", methods=["GET"])
@jwt_required()
def reports():
    keyword = request.args.get("keyword", "", type=str)
    status = request.args.get("status", "", type=str)
    module = request.args.get("module", "", type=str)
    start_date = request.args.get("start_date", "", type=str)
    end_date = request.args.get("end_date", "", type=str)

    query = TestReport.query.join(TestCase, TestReport.case_id == TestCase.id)
    if keyword:
        query = query.filter(TestReport.case_name.like(f"%{keyword}%"))
    if status:
        query = query.filter(TestReport.status == status.upper())
    if module:
        query = query.filter(TestCase.module.like(f"%{module.strip()}%"))
    if start_date:
        query = query.filter(TestReport.create_time >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(TestReport.create_time < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))

    result = paginate(query, order_by=TestReport.id.desc(), page_size=20)
    return success({
        "list": [{
            "id": r.id, "case_name": r.case_name, "status": r.status,
            "time": r.cost_time, "code": r.response_code,
            "msg": r.error_msg,
            "module": r.case.module if r.case else None,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S")
        } for r in result.items],
        "total": result.total, "page": result.page,
        "page_size": result.page_size, "total_pages": result.total_pages,
    })


@test_bp.route("/page")
def test_page():
    return render_template("api_test.html")


@test_bp.route("/page/reports")
def report_page():
    return render_template("report.html")


# 获取报告详情
@test_bp.route("/report/<int:rid>", methods=["GET"])
@jwt_required()
def get_report_detail(rid):
    report = TestReport.query.get(rid)
    if not report:
        raise NotFoundException("报告不存在")
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


@test_bp.route("/batch/run", methods=["POST"])
@jwt_required()
def batch_run():
    uid = int(get_jwt_identity())
    req = validate_request(BatchRunSchema, request.json)
    ids = req["ids"]
    tags_param = req.get("tags", "")

    # 如果传了 tags 参数，按标签筛选用例
    if tags_param:
        tag_list = [t.strip() for t in tags_param.split(",") if t.strip()]
        if tag_list:
            conditions = [TestCase.tags.like(f"%{t}%") for t in tag_list]
            tagged_cases = TestCase.query.filter(or_(*conditions)).all()
            tagged_ids = {c.id for c in tagged_cases}
            ids = [cid for cid in ids if cid in tagged_ids]

    task_id = str(uuid.uuid4())
    task = AsyncTask(
        id=task_id,
        task_type="batch_run",
        status="pending",
        creator_id=uid,
        create_time=datetime.now(),
    )
    db.session.add(task)
    db.session.commit()
    celery_app.send_task("batch_run", args=[ids, uid], task_id=task_id)

    return success({"task_id": task_id}, "批量任务已提交")


@test_bp.route("/batch/<int:bid>/results", methods=["GET"])
@jwt_required()
def get_batch_results(bid):
    batch = BatchTask.query.get(bid)
    if not batch:
        return error("批次不存在")
    results = BatchResult.query.filter_by(batch_id=bid).all()
    return success({
        "batch_id": batch.id,
        "total": batch.total,
        "passed": batch.passed,
        "failed": batch.failed,
        "create_time": batch.create_time.isoformat() if batch.create_time else None,
        "results": [
            {
                "case_id": r.case_id,
                "case_name": r.case_name,
                "status": r.status,
                "cost_time": r.cost_time,
                "response_code": r.response_code,
                "error_msg": r.error_msg,
            }
            for r in results
        ],
    })
