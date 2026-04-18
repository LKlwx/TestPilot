import os
from datetime import timedelta

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get("SECRET_KEY", "testpilot-2026-super-secure-key")
    DEBUG = False
    REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
    # 数据库配置
    # 生产环境可以换成 MySQL/PostgreSQL
    # SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@host/dbname"
    SQLALCHEMY_DATABASE_URI = "sqlite:///testpilot.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 配置（登录鉴权）
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "testpilot-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # 定时任务配置
    SCHEDULER_API_ENABLED = True

    # AI 模型配置 (LM Studio)
    AI_API_BASE = "http://127.0.0.1:1234"  # 本地大模型服务地址
    AI_MODEL = "qwen3.5-9b"  # 模型名称

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
