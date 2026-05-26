from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager

# 数据库实例
db = SQLAlchemy()

# 登录管理器
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

# JWT 鉴权实例
jwt = JWTManager()
