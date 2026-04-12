from flask import request, g
from datetime import datetime
from extensions import db

def register_middleware(app):
    @app.before_request
    def before_request():
        # 请求前钩子：记录请求开始时间和客户端IP
        g.start_time = datetime.now()
        g.ip = request.remote_addr

    @app.after_request
    def after_request(response):
        # 请求后钩子，释放数据库链接，防止内存泄露
        try:
            db.session.remove()
        except:
            pass
        return response
