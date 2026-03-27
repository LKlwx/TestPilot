from flask import Blueprint, render_template, request
from extensions import db
from models import PerformanceCase, PerformanceReport
from core.response import success, error
from service.performance_service import run_performance

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
def add_case():
    try:
        d = request.json
        # 转成int
        concurrency = int(d.get("concurrency", 10))
        total = int(d.get("total", 50))
        case = PerformanceCase(
            name=d["name"],
            url=d["url"],
            method=d.get("method", "GET"),
            headers=d.get("headers", "{}"),
            body=d.get("body"),
            concurrency=concurrency,
            total=total
        )
        db.session.add(case)
        db.session.commit()
        return success(msg="保存成功")
    except Exception as e:
        db.session.rollback()
        return error("保存失败：" + str(e))


# 获取用例列表
@performance_bp.route("/cases", methods=["GET"])
def cases():
    try:
        case_list = PerformanceCase.query.all()
        data = []
        for item in case_list:
            data.append({
                "id": item.id,
                "name": item.name,
                "url": item.url,
                "concurrency": item.concurrency,
                "total": item.total
            })
        return success(data=data)
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
            "create_time": report.create_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return success(data=data)
    except Exception as e:
        return error("获取详情失败：" + str(e))

# 删除用例
@performance_bp.route("/case/<int:cid>", methods=["DELETE"])
def delete_case(cid):
    try:
        case = PerformanceCase.query.get(cid)
        if not case:
            return error("用例不存在")
        db.session.delete(case)
        db.session.commit()
        return success(msg="删除成功")
    except Exception as e:
        db.session.rollback()
        return error("删除失败：" + str(e))
