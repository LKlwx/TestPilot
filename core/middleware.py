from flask import request, g, jsonify
from datetime import datetime
from extensions import db
from core.ratelimit import global_limiter, global_circuit, tiered_limiter
from flask_jwt_extended import get_jwt_identity

def register_middleware(app):
    @app.before_request
    def before_request():
        # 全局限流检查（兜底）
        if not global_limiter.is_allowed():
            return jsonify({"code": 429, "msg": "全局限流触发：请求过于频繁，请稍后再试"}), 429

        # IP 级限流：200 req/min（本地 IP 不限，自压测不影响）
        if request.remote_addr not in ("127.0.0.1", "::1", "localhost"):
            ip_key = f"ip:{request.remote_addr}"
            if not tiered_limiter.is_allowed(ip_key, 200, 60):
                return jsonify({"code": 429, "msg": "IP 级限流触发：请求过于频繁，请稍后再试"}), 429

        # 用户级限流：100 req/min（已登录用户）
        try:
            identity = get_jwt_identity()
            if identity:
                user_key = f"user:{identity}"
                if not tiered_limiter.is_allowed(user_key, 100, 60):
                    return jsonify({"code": 429, "msg": "用户级限流触发：请求过于频繁，请稍后再试"}), 429
        except Exception:
            pass

        # 登录接口限流：5 req/min（防暴力破解）
        if request.path.endswith("/login") and request.method == "POST":
            login_key = f"login:{request.remote_addr}"
            if not tiered_limiter.is_allowed(login_key, 5, 60):
                return jsonify({"code": 429, "msg": "登录限流触发：登录尝试过于频繁，请稍后再试"}), 429

        # 全局熔断检查
        if not global_circuit.is_allowed():
            return jsonify({"code": 503, "msg": "服务暂不可用，请稍后再试"}), 503

        # 请求前钩子：记录请求开始时间和客户端IP
        g.start_time = datetime.now()
        g.ip = request.remote_addr

    @app.after_request
    def after_request(response):
        status_code = response.status_code

        # 请求耗时日志
        if hasattr(g, "start_time"):
            elapsed_ms = round((datetime.now() - g.start_time).total_seconds() * 1000, 1)
            app.logger.info("[%s] %s %s → %s (%.1fms)", g.ip, request.method, request.path, status_code, elapsed_ms)

        if status_code >= 500:
            global_circuit.record_failure()
        elif status_code < 400:
            global_circuit.record_success()

        try:
            db.session.remove()
        except:
            pass
        return response
