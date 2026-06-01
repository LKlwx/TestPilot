from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_caching import Cache

# 数据库实例
db = SQLAlchemy()

# 数据库迁移
migrate = Migrate()

# 缓存（Redis，Dashboard 数据 60s 过期）
cache = Cache()

# 登录管理器
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

# JWT 鉴权实例
jwt = JWTManager()
