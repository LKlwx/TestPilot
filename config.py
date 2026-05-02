import os
from datetime import timedelta

# 获取项目根目录的绝对路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get("SECRET_KEY", "testpilot-2026-super-secure-key")
    DEBUG = False
    # 请求超时时间（秒）
    REQUEST_TIMEOUT = 10
    # 数据库配置（使用绝对路径，避免不同工作目录下数据丢失）
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'testpilot.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 配置（登录鉴权）
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "testpilot-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)  # Access Token 2小时
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)  # Refresh Token 30天

    # AI 模型配置（LM Studio 本地大模型服务）
    AI_API_BASE = "http://127.0.0.1:1234"
    AI_MODEL = "qwen3.5-9b"

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True

class TestConfig(Config):
    """测试环境配置"""
    DEBUG = True
    # 测试环境用独立数据库
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'testpilot_test.db')}"

class DemoConfig(Config):
    """演示环境配置"""
    DEBUG = False
    # 演示环境用独立数据库，数据独立
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'testpilot_demo.db')}"

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False

config = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "demo": DemoConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
