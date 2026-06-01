import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import PerformanceCase, PerformanceReport, User, PerformanceBaseline
from core.exception import NotFoundException
from core.response import success
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
        total=data.get("total", 50),
            ramp_steps=data.get("ramp_steps", 1),
            steady_duration=data.get("steady_duration", 0),
            tags=data.get("tags", ""),
        )
    db.session.add(case)
    with db_write_guard("性能用例添加失败"):
        db.session.flush()
    add_operation_log(user.id, username, "add_perf_case", f"新增性能用例: {data['name']}")
    return success(data={"id": case.id}, msg="保存成功")


# 获取用例列表
@performance_bp.route("/cases", methods=["GET"])
@jwt_required()
def cases():
    keyword = request.args.get("keyword", "", type=str)
    tag = request.args.get("tag", "", type=str)

    query = PerformanceCase.query
    if keyword:
        query = query.filter(PerformanceCase.name.like(f"%{keyword}%"))
    if tag:
        query = query.filter(PerformanceCase.tags.like(f"%{tag.strip()}%"))

    result = paginate(query, order_by=PerformanceCase.id.desc())

    data = []
    for item in result.items:
        data.append({
            "id": item.id,
            "name": item.name,
            "url": item.url,
            "method": item.method,
            "concurrency": item.concurrency,
            "total": item.total,
                "ramp_steps": item.ramp_steps,
                "steady_duration": item.steady_duration,
                "tags": item.tags,
            })

    return success({
        "list": data,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


# 执行压测
@performance_bp.route("/case/<int:cid>/run", methods=["POST"])
@jwt_required()
def run(cid):
    case = PerformanceCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    report = run_performance(case)
    return success(data=report, msg="压测完成")


# 报告列表
@performance_bp.route("/reports", methods=["GET"])
@jwt_required()
def reports():
    keyword = request.args.get("keyword", "", type=str)
    start_date = request.args.get("start_date", "", type=str)
    end_date = request.args.get("end_date", "", type=str)

    query = PerformanceReport.query
    if keyword:
        query = query.filter(PerformanceReport.case_name.like(f"%{keyword}%"))
    if start_date:
        query = query.filter(PerformanceReport.create_time >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(PerformanceReport.create_time < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))

    result = paginate(query, order_by=PerformanceReport.id.desc(), page_size=20)
    return success({
        "list": [{
            "id": r.id, "case_name": r.case_name,
            "concurrency": r.concurrency, "total": r.total,
            "success": r.success, "fail": r.fail,
            "qps": r.qps, "avg_time": r.avg_time,
            "is_local": r.is_local,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S")
        } for r in result.items],
        "total": result.total, "page": result.page,
        "page_size": result.page_size, "total_pages": result.total_pages,
    })


# 报告详情
@performance_bp.route("/report/<int:rid>", methods=["GET"])
@jwt_required()
def report_detail(rid):
    report = PerformanceReport.query.get(rid)
    if not report:
        raise NotFoundException("报告不存在")
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
        "create_time": report.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        "extra": json.loads(report.extra) if report.extra else None,
    }

    baseline = PerformanceBaseline.query.filter_by(case_id=report.case_id).first()
    if baseline and baseline.p90:
        pct = round((report.p90 - baseline.p90) / baseline.p90 * 100, 1) if baseline.p90 else 0
        if pct >= 20:
            level = "severe"
            label = "严重退化"
        elif pct >= 10:
            level = "minor"
            label = "轻微退化"
        elif pct <= -20:
            level = "improved"
            label = "性能提升"
        else:
            level = "stable"
            label = "无明显变化"
        data["degradation"] = {
            "level": level, "label": label, "pct": pct,
            "baseline_p90": round(baseline.p90, 2),
            "baseline_p99": round(baseline.p99, 2) if baseline.p99 else None,
            "baseline_avg": round(baseline.avg_time, 2) if baseline.avg_time else None,
            "baseline_qps": round(baseline.qps, 2) if baseline.qps else None,
        }
    else:
        data["degradation"] = None

    return success(data=data)


@performance_bp.route("/report/<int:rid>/baseline", methods=["POST"])
@jwt_required()
def set_baseline(rid):
    report = PerformanceReport.query.get(rid)
    if not report:
        raise NotFoundException("报告不存在")

    baseline = PerformanceBaseline.query.filter_by(case_id=report.case_id).first()
    if baseline:
        baseline.report_id = report.id
        baseline.p90 = report.p90
        baseline.p99 = report.p99
        baseline.avg_time = report.avg_time
        baseline.qps = report.qps
    else:
        baseline = PerformanceBaseline(
            case_id=report.case_id, report_id=report.id,
            p90=report.p90, p99=report.p99,
            avg_time=report.avg_time, qps=report.qps,
        )
        db.session.add(baseline)
    db.session.commit()
    return success(msg="基线设置成功")


# 删除用例
@performance_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_case(cid):
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = PerformanceCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    case_name = case.name
    db.session.delete(case)
    with db_write_guard("删除压测用例"):
        db.session.flush()
    add_operation_log(user.id, username, "delete_perf_case", f"删除性能用例: {case_name} (ID={cid})")
    return success(msg="删除成功")

# 更新用例
@performance_bp.route("/case/<int:cid>", methods=["PUT"])
@jwt_required()
def update_case(cid):
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    username = user.username if user else "未知"
    case = PerformanceCase.query.get(cid)
    if not case:
        raise NotFoundException("用例不存在")
    old_name = case.name
    old_url = case.url
    old_method = case.method
    old_concurrency = case.concurrency
    old_total = case.total
    d = validate_request(UpdatePerformanceCaseSchema, request.json)

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
    case.ramp_steps = d.get("ramp_steps", case.ramp_steps)
    case.steady_duration = d.get("steady_duration", case.steady_duration)
    case.tags = d.get("tags", case.tags)

    with db_write_guard("修改压测用例"):
        db.session.flush()
    detail = f"修改性能用例: {old_name} → {case.name}"
    if changes:
        detail += "，" + "，".join(changes)
    detail += f" (ID={cid})"
    add_operation_log(user.id, username, "update_perf_case", detail)
    return success(msg="修改成功")
