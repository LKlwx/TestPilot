"""健康检查与就绪探针

- /health: 存活探针，仅返回 200
- /ready: 就绪探针，检测 DB + Redis 是否可达
"""

from flask import Blueprint, jsonify
from config import Config
from extensions import db
from sqlalchemy import text

monitor_bp = Blueprint("monitor", __name__)


@monitor_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@monitor_bp.route("/ready", methods=["GET"])
def ready():
    errors = []
    # 数据库检测
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"db: {str(e)[:50]}")
    # Redis 检测
    try:
        import redis

        r = redis.from_url(Config.REDIS_URL)
        r.ping()
    except Exception:
        errors.append("redis: unreachable")

    if errors:
        return jsonify({"status": "unready", "errors": errors}), 503
    return jsonify({"status": "ready"}), 200
