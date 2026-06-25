from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import NotFound
from config import config
from core.exception import APIException
from core.middleware import register_middleware
from core.response import error
from extensions import db, login_manager, jwt, migrate, cache
from core.blocklist import is_blocklisted
from api.auth import auth_bp
from api.test import test_bp
from api.ui import ui_bp
from api.performance import performance_bp
from api.ai import ai_bp
from api.coverage import coverage_bp
from api.environment import env_bp


def create_app(config_name="default"):
    app = Flask(__name__)
    config_class = config[config_name]
    app.config.from_object(config_class)

    # ===== 启动时强校验密钥 =====
    # 生产环境（production/demo）必须配置强密钥，否则拒绝启动
    is_production = config_name in ("production", "demo")
    config_class.validate_secrets(is_production=is_production)
    # ================================================

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    jwt.init_app(app)

    # CORS 配置
    if config_name == "development":
        CORS(app, origins="*", supports_credentials=True)
    else:
        CORS(app, origins=config_class.CORS_ORIGINS, supports_credentials=True)

    # 初始化缓存（使用 Redis，Dashboard 数据 60s 过期）
    cache.init_app(app, config={
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_URL": config_class.REDIS_URL,
        "CACHE_DEFAULT_TIMEOUT": 60,
    })

    @login_manager.user_loader
    def user_loader(user_id):
        from models import User
        return User.query.get(int(user_id))

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return is_blocklisted(jwt_payload["jti"])

    # 注册全局中间件
    register_middleware(app)

    # 全局异常统一返回
    @app.errorhandler(APIException)
    def handle_api_exception(e):
        return error(e.msg, e.code)

    # 其他全局异常兜底处理
    @app.errorhandler(Exception)
    def handle_all_exception(e):
        if isinstance(e, (SystemExit, KeyboardInterrupt)):
            raise e
        # 404 是正常业务状态码，不记 ERROR 日志
        if isinstance(e, NotFound):
            return error(e.description, 404)
        import traceback
        from core.logger import log_error
        log_error(e, context="全局异常")
        if app.config["DEBUG"]:
            return error(str(e), 500)
        else:
            return error("服务器内部错误", 500)

    # 注册蓝本
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(test_bp, url_prefix="/api/test")
    app.register_blueprint(ui_bp, url_prefix="/api/ui")
    app.register_blueprint(performance_bp, url_prefix="/api/performance")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(coverage_bp, url_prefix="/api/coverage")
    app.register_blueprint(env_bp, url_prefix="/api/env")

    @app.route("/")
    def root_index():
        from flask import redirect
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect("/api/auth/page/home")
        else:
            return redirect("/api/auth/login/page")

    # 防止 favicon.ico 报 404
    @app.route("/favicon.ico")
    def favicon():
        from flask import make_response
        response = make_response("", 204)
        return response

    return app
