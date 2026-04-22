import os
from datetime import timedelta

class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get("SECRET_KEY", "testpilot-2026-super-secure-key")
    DEBUG = False
    # 请求超时时间（秒）
    REQUEST_TIMEOUT = 10
    # 数据库配置（生产环境可切换为 MySQL/PostgreSQL）
    SQLALCHEMY_DATABASE_URI = "sqlite:///testpilot.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 配置（登录鉴权）
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "testpilot-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # AI 模型配置（LM Studio 本地大模型服务）
    AI_API_BASE = "http://127.0.0.1:1234"
    AI_MODEL = "qwen3.5-9b"

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
