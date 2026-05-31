from flask import Blueprint, render_template, request, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import PerformanceCase, PerformanceReport, User
from core.response import success, error
from core.pagination import paginate
from core.db_guard import db_write_guard
from core.schema import validate_request
from core.logger import get_logger
from api.schemas import AddPerformanceCaseSchema, UpdatePerformanceCaseSchema
from service.performance_service import run_performance
from service.operation_log_service import add_operation_log

logger = get_logger(__name__)

performance_bp = Blueprint("performance", __name__)


# 性能测试页面
@performance_bp.route("/page")
def page():
    return render_template("performance.html")


# 性能报告页面
@performance_bp.route("/page/reports")
def reports_page():
    return render_template("performance_report.html")


@performance_bp.route("/reports/page")
def old_reports_page():
    return redirect("/api/performance/page/reports")


# 新增性能用例
@performance_bp.route("/case", methods=["POST"])
@jwt_required()
def add_case():
    try:
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        username = user.username if user else "未知"
        data = validate_request(AddPerformanceCaseSchema, request.json)
        case = PerformanceCase(
            name=data["name"],
            url=data["url"],
            method=data.get("method", "GET"),
            headers=data.get("headers", "{}"),
            body=data.get("body"),
            concurrency=data.get("concurrency", 10),
            total=data.get("total", 50)
        )
        db.session.add(case)
        with db_write_guard("性能用例添加失败"):
            db.session.flush()
        add_operation_log(user.id, username, "add_perf_case", f"新增性能用例: {data['name']}")
        return success(data={"id": case.id}, msg="保存成功")
    except Exception as e:
        return error("保存失败")


# 获取用例列表
@performance_bp.route("/cases", methods=["GET"])
@jwt_required()
def cases():
    try:
        keyword = request.args.get("keyword", "", type=str)

        query = PerformanceCase.query
        if keyword:
            query = query.filter(PerformanceCase.name.like(f"%{keyword}%"))

        result = paginate(query, order_by=PerformanceCase.id.desc())

        data = []
        for item in result.items:
            data.append({
                "id": item.id,
                "name": item.name,
                "url": item.url,
                "method": item.method,
                "concurrency": item.concurrency,
                "total": item.total
            })

        return success({
            "list": data,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "total_pages": result.total_pages,
        })
    except Exception as e:
        logger.error("获取压测用例列表失败: %s", str(e), exc_info=True)
        return error("服务器内部错误，请查看日志")


# 执行压测
@performance_bp.route("/case/<int:cid>/run", methods=["POST"])
@jwt_required()
def run(cid):
    try:
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        report = run_performance(case)
        return success(data=report, msg="压测完成")
    except Exception as e:
        logger.error("压测执行失败: %s", str(e), exc_info=True)
        return error("服务器内部错误，请查看日志")


# 报告列表
@performance_bp.route("/reports", methods=["GET"])
@jwt_required()
def reports():
    try:
        report_list = PerformanceReport.query.order_by(PerformanceReport.id.desc()).limit(20).all()
        data = []
        for item in report_list:
            data.append({
                "id": item.id,
                "case_name": item.case_name,
                "concurrency": item.concurrency,
                "total": item.total,
                "success": item.success,
                "fail": item.fail,
                "qps": item.qps,
                "avg_time": item.avg_time,
                "is_local": item.is_local,
                "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S")
            })
        return success(data=data)
    except Exception as e:
        logger.error("获取压测报告列表失败: %s", str(e), exc_info=True)
        return error("服务器内部错误，请查看日志")


# 报告详情
@performance_bp.route("/report/<int:rid>", methods=["GET"])
@jwt_required()
def report_detail(rid):
    try:
        report = PerformanceReport.query.get(rid)
        if not report:
            return error("报告不存在")
        data = {
            "id": report.id,
            "case_name": report.case_name,
            "concurrency": report.concurrency,
            "total": report.total,
            "success": report.success,
            "fail": report.fail,
            "qps": report.qps,
            "avg_time": report.avg_time,
            "min_time": report.min_time,
            "max_time": report.max_time,
            "p90": report.p90,
            "p99": report.p99,
            "success_rate": report.success_rate,
            "is_local": report.is_local,
            "create_time": report.create_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return success(data=data)
    except Exception as e:
        logger.error("获取压测报告详情失败: %s", str(e), exc_info=True)
        return error("服务器内部错误，请查看日志")

# 删除用例
@performance_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_case(cid):
    try:
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        username = user.username if user else "未知"
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        case_name = case.name
        db.session.delete(case)
        with db_write_guard("删除压测用例"):
            db.session.flush()
        add_operation_log(user.id, username, "delete_perf_case", f"删除性能用例: {case_name} (ID={cid})")
        return success(msg="删除成功")
    except Exception as e:
        return error("服务器内部错误，请查看日志")

# 更新用例
@performance_bp.route("/case/<int:cid>", methods=["PUT"])
@jwt_required()
def update_case(cid):
    try:
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        username = user.username if user else "未知"
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        old_name = case.name
        old_url = case.url
        old_method = case.method
        old_concurrency = case.concurrency
        old_total = case.total
        d = validate_request(UpdatePerformanceCaseSchema, request.json)

        # 记录修改的字段
        changes = []
        new_name = d.get("name", case.name)
        new_url = d.get("url", case.url)
        new_method = d.get("method", case.method)
        new_concurrency = d.get("concurrency", case.concurrency)
        new_total = d.get("total", case.total)

        if old_name != new_name:
            changes.append(f"名称({old_name}→{new_name})")
        if old_url != new_url:
            changes.append(f"URL({old_url[:30]}...→{new_url[:30]}...)")
        if old_method != new_method:
            changes.append(f"方法({old_method}→{new_method})")
        if old_concurrency != new_concurrency:
            changes.append(f"并发({old_concurrency}→{new_concurrency})")
        if old_total != new_total:
            changes.append(f"总请求数({old_total}→{new_total})")

        case.name = new_name
        case.url = new_url
        case.method = new_method
        case.headers = d.get("headers", "{}")
        case.body = d.get("body")
        case.concurrency = new_concurrency
        case.total = new_total

        with db_write_guard("修改压测用例"):
            db.session.flush()
        detail = f"修改性能用例: {old_name} → {case.name}"
        if changes:
            detail += "，" + "，".join(changes)
        detail += f" (ID={cid})"
        add_operation_log(user.id, username, "update_perf_case", detail)
        return success(msg="修改成功")
    except Exception as e:
        return error("服务器内部错误，请查看日志")
