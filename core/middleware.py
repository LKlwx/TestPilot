from flask import request, g, jsonify
from datetime import datetime
from extensions import db
from core.ratelimit import global_limiter, global_circuit

def register_middleware(app):
    @app.before_request
    def before_request():
        # 1. 全局限流检查
        if not global_limiter.is_allowed():
            return jsonify({"code": 429, "msg": "请求过于频繁，请稍后再试"}), 429
        
        # 2. 全局熔断检查
        if not global_circuit.is_allowed():
            return jsonify({"code": 503, "msg": "服务暂不可用，请稍后再试"}), 503
        
        # 请求前钩子：记录请求开始时间和客户端IP
        g.start_time = datetime.now()
        g.ip = request.remote_addr

    @app.after_request
    def after_request(response):
        # 请求后钩子：根据状态码记录结果
        status_code = response.status_code
        
        # 只记录5xx错误为失败
        if status_code >= 500:
            global_circuit.record_failure()  # 5xx算失败
        elif status_code < 400:
            global_circuit.record_success()  # 2xx/3xx算成功
        
        # 请求后钩子，释放数据库链接，防止内存泄露
        try:
            db.session.remove()
        except:
            pass
        return response
