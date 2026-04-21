from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, request, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity

from core.exception import NotFoundException
from core.response import success, error
from models import TestCase, TestReport
from extensions import db
from service.test_service import execute_test_case
from api.auth import add_operation_log

test_bp = Blueprint("test", __name__)


@test_bp.route("/cases", methods=["GET"])
def get_cases():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    keyword = request.args.get("keyword", "", type=str)

    query = TestCase.query
    if keyword:
        query = query.filter(TestCase.name.like(f"%{keyword}%"))

    total = query.count()
    cases = query.order_by(TestCase.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [{
        "id": c.id,
        "name": c.name,
        "module": c.module,
        "method": c.method,
        "url": c.url,
        "expect": c.expect
    } for c in cases]

    return success({
        "list": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })


@test_bp.route("/case", methods=["POST"])
@jwt_required()
def add_case():
    from models import User
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
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
        add_operation_log(user.id, username, "add_case", f"新增接口用例: {data['name']}")
    except Exception as e:
        db.session.rollback()
        print(f"接口用例添加失败:{e}")
        return error("保存失败")
    return success(msg="成功")


@test_bp.route("/case/<int:cid>/run", methods=["POST"])
def run_case(cid):
    case = TestCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    res = execute_test_case(case)
    return success(res)


@test_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_case(cid):
    from models import User
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
    from models import User
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = TestCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    old_name = case.name
    data = request.get_json()
    case.name = data.get("name", case.name)
    case.method = data.get("method", case.method)
    case.url = data.get("url", case.url)
    case.headers = data.get("headers", case.headers)
    case.body = data.get("body", case.body)
    case.expect = data.get("expect", case.expect)
    case.extract_var = data.get("extract_var", case.extract_var)
    db.session.commit()
    add_operation_log(user.id, username, "update_case", f"修改接口用例: {old_name} → {case.name} (ID={cid})")
    return success(msg="更新成功")


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


# 批量执行
@test_bp.route("/batch/run", methods=["POST"])
def batch_run():
    from app import create_app
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

    with ThreadPoolExecutor(max_workers=5) as executor:
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
                    "case_id": cid,
                    "status": "ERROR",
                    "msg": str(e),
                })
    return success(res_list, "批量执行完成")
