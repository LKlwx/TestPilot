from datetime import datetime
import re
from urllib.parse import urlparse
from flask import Blueprint, request, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from core.response import success
from core.exception import APIException, NotFoundException
from core.pagination import paginate
from models import ApiCoverage
from extensions import db

coverage_bp = Blueprint("coverage", __name__)


@coverage_bp.route("/page")
def coverage_page():
    return render_template("api_coverage.html")


def _normalize_path(url):
    """从完整 URL 提取路径（去 query/fragment）"""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return path


def _mark_covered(method: str, url: str, user_id: int):
    """根据 method + URL 标记 API 覆盖"""
    path = _normalize_path(url)

    # 1. 精确路径匹配
    record = ApiCoverage.query.filter_by(method=method.upper(), path=path).first()
    if record:
        if not record.is_covered:
            record.is_covered = True
            record.covered_by = user_id
            record.covered_time = datetime.now()
        return True

    candidates = ApiCoverage.query.filter_by(method=method.upper()).all()
    for c in candidates:
        pattern = re.sub(r"\{[^}]+\}|:[^/]+", r"[^/]+", c.path)
        pattern = "^" + re.escape(pattern).replace(r"\[\^/\]\+", "[^/]+") + "$"
        if re.match(pattern, path):
            if not c.is_covered:
                c.is_covered = True
                c.covered_by = user_id
                c.covered_time = datetime.now()
            return True

    return False


@coverage_bp.route("/stats", methods=["GET"])
@jwt_required()
def coverage_stats():
    """覆盖率统计"""
    total = ApiCoverage.query.count()
    covered = ApiCoverage.query.filter_by(is_covered=True).count()
    return success({
        "total": total,
        "covered": covered,
        "rate": round(covered / total * 100, 1) if total > 0 else 0,
    })


@coverage_bp.route("/list", methods=["GET"])
@jwt_required()
def coverage_list():
    keyword = request.args.get("keyword", "", type=str)
    query = ApiCoverage.query
    if keyword:
        query = query.filter(ApiCoverage.path.like(f"%{keyword}%"))
    result = paginate(query, order_by=ApiCoverage.create_time.desc())
    return success({
        "list": [{
            "id": r.id, "method": r.method, "path": r.path,
            "summary": r.summary, "is_covered": r.is_covered,
            "covered_time": r.covered_time.strftime("%Y-%m-%d %H:%M") if r.covered_time else None,
        } for r in result.items],
        "total": result.total, "page": result.page,
        "page_size": result.page_size, "total_pages": result.total_pages,
    })


@coverage_bp.route("/import", methods=["POST"])
@jwt_required()
def import_swagger():
    """从 Swagger/OpenAPI JSON 导入接口列表"""
    data = request.json
    if not data:
        raise APIException("请上传 Swagger JSON")

    paths = data.get("paths", data.get("apis", {}))
    if not paths:
        raise APIException("Swagger JSON 中未找到 paths 字段")

    count = 0
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            summary = detail.get("summary", "") if isinstance(detail, dict) else ""
            normalized = _normalize_path(path)
            exists = ApiCoverage.query.filter_by(method=method.upper(), path=normalized).first()
            if not exists:
                api = ApiCoverage(
                    method=method.upper(), path=normalized,
                    summary=summary, is_covered=False,
                )
                db.session.add(api)
                count += 1

    db.session.commit()
    return success(data={"imported": count}, msg=f"导入成功，新增 {count} 个接口")


@coverage_bp.route("/<int:aid>", methods=["DELETE"])
@jwt_required()
def delete_coverage(aid):
    cov = ApiCoverage.query.get(aid)
    if not cov:
        raise NotFoundException("记录不存在")
    db.session.delete(cov)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return success(msg="删除成功")
