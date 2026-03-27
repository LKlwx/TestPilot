from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
# from flask_apscheduler import APScheduler

# 数据库
db = SQLAlchemy()

# 登录管理
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

# JWT 鉴权
jwt = JWTManager()

# 定时任务调度器
# scheduler = APScheduler()
