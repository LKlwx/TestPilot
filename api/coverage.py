import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from core.exception import APIException, NotFoundException
from core.pagination import paginate
from core.response import success
from extensions import db
from models import ApiContract, ApiCoverage, TestCase

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
    return success(
        {
            "total": total,
            "covered": covered,
            "rate": round(covered / total * 100, 1) if total > 0 else 0,
        }
    )


@coverage_bp.route("/list", methods=["GET"])
@jwt_required()
def coverage_list():
    keyword = request.args.get("keyword", "", type=str)
    query = ApiCoverage.query
    if keyword:
        query = query.filter(ApiCoverage.path.like(f"%{keyword}%"))
    result = paginate(query, order_by=ApiCoverage.create_time.desc())
    return success(
        {
            "list": [
                {
                    "id": r.id,
                    "method": r.method,
                    "path": r.path,
                    "summary": r.summary,
                    "is_covered": r.is_covered,
                    "covered_time": r.covered_time.strftime("%Y-%m-%d %H:%M") if r.covered_time else None,
                }
                for r in result.items
            ],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "total_pages": result.total_pages,
        }
    )


def _resolve_schema_refs(obj, schemas, visited=None):
    """递归解析 $ref，返回完整 Schema 定义

    Args:
        obj: 当前解析的 Schema 片段（dict 或 list）
        schemas: 整个 components.schemas 字典
        visited: 已访问的 $ref 路径，防循环引用

    Returns:
        解析后的完整 Schema
    """
    if visited is None:
        visited = set()
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref_path = obj["$ref"]
            if ref_path in visited:
                return {"type": "object"}
            visited.add(ref_path)
            # 支持 #/components/schemas/Xxx
            parts = ref_path.lstrip("#/").split("/")
            # 若 schemas 已经是平铺的 {SchemaName: {...}}，跳过 components/schemas 前缀
            if len(parts) >= 3 and parts[0] == "components" and parts[1] == "schemas":
                parts = parts[2:]
            ref_obj = schemas
            for p in parts:
                ref_obj = ref_obj.get(p, {})
            result = _resolve_schema_refs(ref_obj, schemas, visited)
            visited.discard(ref_path)
            return result
        return {k: _resolve_schema_refs(v, schemas, visited) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_schema_refs(v, schemas, visited) for v in obj]
    return obj


def _compute_schema_hash(schema):
    """计算 Schema 的 SHA256 摘要"""
    raw = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _extract_contract(method, path, summary, swagger_data):
    """从 Swagger 数据中提取该接口的响应 Schema

    查找 path[method].responses[200|201].content['application/json'].schema
    或 path[method].responses[200|201].schema
    """
    schemas = swagger_data.get("components", {}).get("schemas", {})
    methods_data = swagger_data.get("paths", {}).get(path, {})
    method_data = methods_data.get(method.lower(), methods_data.get(method.upper(), {}))

    # 找 response schema
    responses = method_data.get("responses", {})
    response_schema = None
    for status in ("200", "201", "default"):
        resp = responses.get(status, {})
        # OpenAPI 3.x: content['application/json'].schema
        content = resp.get("content", {})
        if content:
            json_content = content.get("application/json", {})
            schema = json_content.get("schema")
            if schema:
                response_schema = _resolve_schema_refs(schema, schemas)
                break
        # OpenAPI 2.x (Swagger): schema 直接挂在 response 下
        schema = resp.get("schema")
        if schema:
            response_schema = _resolve_schema_refs(schema, schemas)
            break

    return response_schema


@coverage_bp.route("/import", methods=["POST"])
@jwt_required()
def import_swagger():
    """从 Swagger/OpenAPI JSON 导入接口列表 + 契约"""
    data = request.json
    if not data:
        raise APIException("请上传 Swagger JSON")

    paths = data.get("paths", data.get("apis", {}))
    if not paths:
        raise APIException("Swagger JSON 中未找到 paths 字段")

    # 批量导入
    imported = 0
    contracted = 0
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            summary = detail.get("summary", "") if isinstance(detail, dict) else ""
            normalized = _normalize_path(path)

            # 1. 写入覆盖率
            exists_api = ApiCoverage.query.filter_by(method=method.upper(), path=normalized).first()
            if not exists_api:
                api = ApiCoverage(
                    method=method.upper(),
                    path=normalized,
                    summary=summary,
                    is_covered=False,
                )
                db.session.add(api)
                imported += 1

            # 2. 写入契约
            endpoint = f"{method.upper()} {normalized}"
            contract = ApiContract.query.filter_by(endpoint=endpoint).first()
            response_schema = _extract_contract(method, path, summary, data)

            if response_schema:
                new_hash = _compute_schema_hash(response_schema)
                if contract:
                    contract.summary = summary
                    contract.response_schema = response_schema
                    contract.schema_hash = new_hash
                    contract.last_version += 1
                    contract.update_time = datetime.now()
                else:
                    db.session.add(
                        ApiContract(
                            endpoint=endpoint,
                            summary=summary,
                            response_schema=response_schema,
                            schema_hash=new_hash,
                            last_version=1,
                        )
                    )
                contracted += 1

    db.session.commit()
    return success(
        data={"imported": imported, "contracted": contracted},
        msg=f"导入成功，新增 {imported} 个接口，{contracted} 个契约",
    )


@coverage_bp.route("/generate-cases", methods=["POST"])
@jwt_required()
def generate_cases_from_swagger():
    """从已导入的 Swagger 数据生成接口用例

    从 ApiCoverage 读取已导入的接口列表，自动创建 TestCase。
    已存在同名+同 URL 的用例跳过不重复创建。
    """
    data = request.json
    if not data or not data.get("paths"):
        raise APIException("请上传 Swagger JSON")

    paths = data.get("paths", {})
    count = 0
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            summary = detail.get("summary", "") if isinstance(detail, dict) else ""
            normalized = _normalize_path(path)

            # 跳过已存在的用例（同名 + 同 method + 同 url）
            exists = TestCase.query.filter_by(name=summary, method=method.upper(), url=normalized).first()
            if exists or not summary:
                continue

            # 从 swagger 提取示例 body（如果有 example）
            body_schema = detail.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            schemas = data.get("components", {}).get("schemas", {})
            resolved = _resolve_schema_refs(body_schema, schemas) if body_schema else None
            sample_body = _schema_to_example(resolved) if resolved else "{}"

            case = TestCase(
                name=summary,
                module="Swagger导入",
                method=method.upper(),
                url=normalized,
                headers="{}",
                body=json.dumps(sample_body) if isinstance(sample_body, (dict, list)) else (sample_body or "{}"),
                expect="",
                extract_var="",
            )
            db.session.add(case)
            count += 1

    db.session.commit()
    return success(data={"generated": count}, msg=f"生成成功，新增 {count} 条用例")


def _schema_to_example(schema):
    """从 JSON Schema 生成示例值（仅用于导入时填充 body 占位）"""
    if schema is None:
        return None
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        return {k: _schema_to_example(v) if isinstance(v, dict) else None for k, v in props.items()}
    if t == "array":
        items = schema.get("items", {})
        return [_schema_to_example(items)] if items else []
    if t == "string":
        enum = schema.get("enum")
        return enum[0] if enum else "string"
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return True
    return None


# ========== 契约查询 ==========


@coverage_bp.route("/contracts", methods=["GET"])
@jwt_required()
def get_contracts():
    keyword = request.args.get("keyword", "", type=str)
    query = ApiContract.query
    if keyword:
        query = query.filter(ApiContract.endpoint.like(f"%{keyword}%"))
    result = paginate(query, order_by=ApiContract.id.desc())
    return success(
        {
            "list": [
                {
                    "id": c.id,
                    "endpoint": c.endpoint,
                    "summary": c.summary,
                    "version": c.last_version,
                    "has_schema": c.response_schema is not None,
                    "update_time": c.update_time.strftime("%Y-%m-%d %H:%M") if c.update_time else None,
                }
                for c in result.items
            ],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "total_pages": result.total_pages,
        }
    )


@coverage_bp.route("/contract/<int:cid>", methods=["GET"])
@jwt_required()
def get_contract(cid):
    contract = ApiContract.query.get(cid)
    if not contract:
        raise NotFoundException("契约不存在")
    return success(
        {
            "id": contract.id,
            "endpoint": contract.endpoint,
            "summary": contract.summary,
            "version": contract.last_version,
            "request_schema": contract.request_schema,
            "response_schema": contract.response_schema,
            "create_time": contract.create_time.isoformat() if contract.create_time else None,
            "update_time": contract.update_time.isoformat() if contract.update_time else None,
        }
    )


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
