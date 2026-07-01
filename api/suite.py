from flask import Blueprint, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from core.db_guard import db_write_guard
from core.exception import APIException, NotFoundException
from core.response import success
from extensions import db
from models import TestCase, TestSuite, TestTask, User, suite_case_association

suite_bp = Blueprint("suite", __name__)


@suite_bp.route("/page")
def suite_page():
    return render_template("suite.html")


@suite_bp.route("/list", methods=["GET"])
@jwt_required()
def get_suites():
    suites = TestSuite.query.order_by(TestSuite.id.desc()).all()
    return success(
        {
            "list": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description or "",
                    "case_count": db.session.query(suite_case_association).filter_by(suite_id=s.id).count(),
                    "create_time": s.create_time.strftime("%Y-%m-%d %H:%M") if s.create_time else None,
                }
                for s in suites
            ],
        }
    )


@suite_bp.route("/<int:sid>", methods=["GET"])
@jwt_required()
def get_suite(sid):
    s = TestSuite.query.get(sid)
    if not s:
        raise NotFoundException("套件不存在")
    rows = (
        db.session.query(suite_case_association)
        .filter_by(suite_id=sid)
        .order_by(suite_case_association.c.suite_id)
        .all()
    )
    cases = []
    for row in rows:
        case = None
        if row.case_type == "api":
            case = TestCase.query.get(row.case_id)
        if case:
            cases.append({"type": row.case_type, "id": case.id, "name": case.name})
    return success(
        {
            "id": s.id,
            "name": s.name,
            "description": s.description or "",
            "cases": cases,
            "create_time": s.create_time.strftime("%Y-%m-%d %H:%M") if s.create_time else None,
        }
    )


@suite_bp.route("/add", methods=["POST"])
@jwt_required()
def add_suite():
    data = request.get_json()
    if not data or not data.get("name"):
        raise APIException("套件名称不能为空")
    suite = TestSuite(
        name=data["name"],
        description=data.get("description", ""),
        creator_id=int(get_jwt_identity()),
    )
    with db_write_guard("套件添加失败"):
        db.session.add(suite)
        db.session.flush()
        _sync_cases(suite, data.get("cases", []))
    return success(data={"id": suite.id}, msg="套件创建成功")


@suite_bp.route("/<int:sid>", methods=["PUT"])
@jwt_required()
def update_suite(sid):
    s = TestSuite.query.get(sid)
    if not s:
        raise NotFoundException("套件不存在")
    data = request.get_json()
    if "name" in data:
        if not data["name"]:
            raise APIException("套件名称不能为空")
        s.name = data["name"]
    s.description = data.get("description", s.description)
    if "cases" in data:
        _sync_cases(s, data["cases"])
    with db_write_guard("套件更新失败"):
        db.session.flush()
    return success(msg="更新成功")


@suite_bp.route("/<int:sid>", methods=["DELETE"])
@jwt_required()
def delete_suite(sid):
    s = TestSuite.query.get(sid)
    if not s:
        raise NotFoundException("套件不存在")
    db.session.execute(suite_case_association.delete().where(suite_case_association.c.suite_id == sid))
    db.session.delete(s)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return success(msg="删除成功")


@suite_bp.route("/<int:sid>/run", methods=["POST"])
@jwt_required()
def run_suite(sid):
    """执行套件：按顺序运行所有 API 用例，共享 ExecutionContext"""
    from core.execution_context import ExecutionContext
    from service.test_service import execute_test_case

    s = TestSuite.query.get(sid)
    if not s:
        raise NotFoundException("套件不存在")
    rows = (
        db.session.query(suite_case_association)
        .filter_by(suite_id=sid)
        .order_by(suite_case_association.c.suite_id)
        .all()
    )
    if not rows:
        return success({"results": [], "total": 0}, msg="套件中没有用例")

    ctx = ExecutionContext()
    results = []
    passed = 0
    for row in rows:
        if row.case_type != "api":
            continue
        case = TestCase.query.get(row.case_id)
        if not case:
            continue
        try:
            res = execute_test_case(case, context=ctx)
            res["case_name"] = case.name
            results.append(res)
            if res.get("status") in ("PASS", "FLAKY"):
                passed += 1
        except Exception as e:
            results.append({"case_name": case.name, "status": "ERROR", "error": str(e)})

    return success(
        {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
        }
    )


def _sync_cases(suite, cases):
    """同步套件关联的用例列表"""
    db.session.execute(suite_case_association.delete().where(suite_case_association.c.suite_id == suite.id))
    for item in cases:
        db.session.execute(
            suite_case_association.insert().values(
                suite_id=suite.id,
                case_type=item.get("type", "api"),
                case_id=item.get("id"),
            )
        )
