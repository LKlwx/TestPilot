from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from core.response import success
from core.exception import APIException, NotFoundException
from core.db_guard import db_write_guard
from models import Environment, TestCase, UICase, PerformanceCase
from extensions import db

env_bp = Blueprint("env", __name__)


@env_bp.route("/list", methods=["GET"])
@jwt_required()
def get_environments():
    envs = Environment.query.order_by(Environment.id.desc()).all()
    return success({
        "list": [{
            "id": e.id, "name": e.name, "base_url": e.base_url,
            "headers": e.headers, "variables": e.variables,
            "is_default": e.is_default,
            "create_time": e.create_time.strftime("%Y-%m-%d %H:%M") if e.create_time else None,
        } for e in envs],
    })


@env_bp.route("/add", methods=["POST"])
@jwt_required()
def add_environment():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("base_url"):
        raise APIException("环境名称和基地址不能为空")

    # 如果设置了默认，先清除其他默认
    if data.get("is_default"):
        for e in Environment.query.filter_by(is_default=True).all():
            e.is_default = False

    env = Environment(
        name=data["name"],
        base_url=data["base_url"].rstrip("/"),
        headers=data.get("headers", "{}"),
        variables=data.get("variables", "{}"),
        is_default=data.get("is_default", False),
    )
    with db_write_guard("环境添加失败"):
        db.session.add(env)
        db.session.flush()
    return success(data={"id": env.id}, msg="环境添加成功")


@env_bp.route("/<int:eid>", methods=["PUT"])
@jwt_required()
def update_environment(eid):
    env = Environment.query.get(eid)
    if not env:
        raise NotFoundException("环境不存在")
    data = request.get_json()

    if "is_default" in data and data["is_default"]:
        for e in Environment.query.filter(Environment.id != eid, Environment.is_default == True).all():
            e.is_default = False

    env.name = data.get("name", env.name)
    env.base_url = data.get("base_url", env.base_url).rstrip("/")
    env.headers = data.get("headers", env.headers)
    env.variables = data.get("variables", env.variables)
    env.is_default = data.get("is_default", env.is_default)
    db.session.commit()
    return success(msg="环境更新成功")


@env_bp.route("/<int:eid>", methods=["DELETE"])
@jwt_required()
def delete_environment(eid):
    env = Environment.query.get(eid)
    if not env:
        raise NotFoundException("环境不存在")
    # 解绑所有关联用例
    for model in (TestCase, UICase, PerformanceCase):
        model.query.filter_by(env_id=eid).update({"env_id": None})
    db.session.delete(env)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return success(msg="环境删除成功")


def resolve_environment(case, context):
    """获取用例绑定的环境，拼接 base_url + case.url

    若用例有 env_id，则取对应环境的 base_url 拼接；
    否则取默认环境 base_url 拼接；
    若无默认环境，则 case.url 必须是完整 URL，保持不变。

    Returns:
        (final_url, env_headers) — 拼接后的 URL 和环境全局请求头
    """
    env_id = getattr(case, "env_id", None)
    env = None
    if env_id:
        env = Environment.query.get(env_id)
    if not env:
        env = Environment.query.filter_by(is_default=True).first()

    url = getattr(case, "url", "")
    if env:
        url = url if url.startswith("http") else f"{env.base_url}{url}"
        env_headers = env.headers or "{}"
        # 环境变量注入到 ExecutionContext
        if env.variables and context:
            try:
                import json
                for k, v in json.loads(env.variables).items():
                    if not context.get_var(k):
                        context.set_var(k, v)
            except (json.JSONDecodeError, TypeError):
                pass
    else:
        env_headers = "{}"

    return url, env_headers
