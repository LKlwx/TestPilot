from email.policy import strict

from flask import Flask
from config import config
from core.exception import APIException
from core.middleware import register_middleware
from core.response import error
from extensions import db, login_manager, jwt
from api.auth import auth_bp
from api.test import test_bp
from api.ui import ui_bp
from api.performance import performance_bp
from api.ai import ai_bp


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)

    # scheduler.init_app(app)

    @login_manager.user_loader
    def user_loader(user_id):
        from models import User
        return User.query.get(int(user_id))

    # 注册全局中间件
    register_middleware(app)

    # 全局异常统一返回
    @app.errorhandler(APIException)
    def handle_api_exception(e):
        return error(e.msg, e.code)

    @app.route("/favicon.ico")
    def favicon():
        return "", 204
    def handle_all_exception(e):
        import traceback
        traceback.print_exc()
        return error(str(e), 500)

    # 登录路由
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(test_bp, url_prefix="/api/test")
    app.register_blueprint(ui_bp, url_prefix="/api/ui")
    app.register_blueprint(performance_bp, url_prefix="/api/performance")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")

    @app.route("/")
    def root_index():
        from flask import redirect
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect("/api/auth/home")
        else:
            return redirect("/api/auth/login/page")

    return app
