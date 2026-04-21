from flask import Blueprint, render_template, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import PerformanceCase, PerformanceReport
from core.response import success, error
from service.performance_service import run_performance
from api.auth import add_operation_log

performance_bp = Blueprint("performance", __name__)


# 性能测试页面
@performance_bp.route("/page")
def page():
    return render_template("performance.html")


# 性能报告页面
@performance_bp.route("/reports/page")
def reports_page():
    return render_template("performance_report.html")


# 新增性能用例
@performance_bp.route("/case", methods=["POST"])
@jwt_required()
def add_case():
    from models import User
    try:
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        username = user.username if user else "未知"
        data = request.json
        if not data or not data.get("name") or not data.get("url"):
            return error("参数不完整!")
        concurrency = int(data.get("concurrency", 10))
        total = int(data.get("total", 50))
        case = PerformanceCase(
            name=data["name"],
            url=data["url"],
            method=data.get("method", "GET"),
            headers=data.get("headers", "{}"),
            body=data.get("body"),
            concurrency=concurrency,
            total=total
        )
        db.session.add(case)
        db.session.commit()
        add_operation_log(user.id, username, "add_perf_case", f"新增性能用例: {data['name']}")
        return success(msg="保存成功")
    except Exception as e:
        db.session.rollback()
        print(f"性能用例添加失败:{e}")
        return error("保存失败")


# 获取用例列表
@performance_bp.route("/cases", methods=["GET"])
def cases():
    try:
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 10, type=int)
        keyword = request.args.get("keyword", "", type=str)

        query = PerformanceCase.query
        if keyword:
            query = query.filter(PerformanceCase.name.like(f"%{keyword}%"))

        total = query.count()
        case_list = query.order_by(PerformanceCase.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

        data = []
        for item in case_list:
            data.append({
                "id": item.id,
                "name": item.name,
                "url": item.url,
                "concurrency": item.concurrency,
                "total": item.total
            })

        return success({
            "list": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        return error("获取用例失败：" + str(e))


# 执行压测
@performance_bp.route("/case/<int:cid>/run", methods=["POST"])
def run(cid):
    try:
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        report = run_performance(case)
        return success(data=report, msg="压测完成")
    except Exception as e:
        return error("执行失败：" + str(e))


# 报告列表
@performance_bp.route("/reports", methods=["GET"])
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
                "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S")
            })
        return success(data=data)
    except Exception as e:
        return error("获取报告失败：" + str(e))


# 报告详情
@performance_bp.route("/report/<int:rid>", methods=["GET"])
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
            "create_time": report.create_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return success(data=data)
    except Exception as e:
        return error("获取详情失败：" + str(e))

# 删除用例
@performance_bp.route("/case/<int:cid>", methods=["DELETE"])
@jwt_required()
def delete_case(cid):
    try:
        from models import User
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        username = user.username if user else "未知"
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        case_name = case.name
        db.session.delete(case)
        db.session.commit()
        add_operation_log(user.id, username, "delete_perf_case", f"删除性能用例: {case_name} (ID={cid})")
        return success(msg="删除成功")
    except Exception as e:
        db.session.rollback()
        return error("删除失败：" + str(e))

# 更新用例
@performance_bp.route("/case/<int:cid>", methods=["PUT"])
@jwt_required()
def update_case(cid):
    from models import User
    try:
        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        username = user.username if user else "未知"
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        old_name = case.name
        d = request.json
        case.name = d["name"]
        case.url = d["url"]
        case.method = d.get("method", "GET")
        case.headers = d.get("headers", "{}")
        case.body = d.get("body")
        case.concurrency = int(d.get("concurrency", 10))
        case.total = int(d.get("total", 50))
        db.session.commit()
        add_operation_log(user.id, username, "update_perf_case", f"修改性能用例: {old_name} → {case.name} (ID={cid})")
        return success(msg="修改成功")
    except Exception as e:
        db.session.rollback()
        return error("修改失败：" + str(e))
