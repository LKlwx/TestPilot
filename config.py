import os
import sys
from datetime import timedelta

# 获取项目根目录的绝对路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 弱密钥黑名单（启动时会被拒绝）
_WEAK_KEY_BLACKLIST = {
    "testpilot-jwt-secret",
    "testpilot-2026-super-secure-key",
    "secret",
    "jwt-secret",
    "password",
    "123456",
    "admin",
    "default",
}


def _validate_secret_key(key_name: str, key_value: str, is_production: bool) -> None:
    """
    校验密钥强度
    
    规则：
    1. 生产环境：强制要求从环境变量读取，禁止使用默认值
    2. 密钥长度 >= 32 字符
    3. 密钥不能是常见弱密钥
    4. 开发环境：允许使用默认值，但打印警告
    """
    # 检查是否是默认值（环境变量未设置时使用的值）
    is_default = key_value in _WEAK_KEY_BLACKLIST or len(key_value) < 32
    
    if is_production and is_default:
        # 生产环境使用默认密钥 = 直接拒绝启动
        raise RuntimeError(
            f"FATAL ERROR: {key_name} 使用了弱密钥或默认值！\n"
            f"当前值: {key_value[:10]}...\n"
            f"生产环境必须设置强密钥，请执行以下操作之一：\n"
            f"  1. 设置环境变量：export {key_name}=<your-strong-secret-key>\n"
            f"  2. 或使用随机生成：export {key_name}=$(openssl rand -base64 32)"
        )
    
    if is_default:
        import logging
        logging.warning("WARNING: %s 使用了默认弱密钥！这会导致 JWT Token 可被伪造，存在严重安全隐患。请在生产环境前设置强密钥：export %s=$(openssl rand -base64 32)", key_name, key_name)


class Config:
    """基础配置类"""
    # 默认密钥（仅用于开发环境，生产环境会被拒绝启动）
    _DEFAULT_SECRET_KEY = "testpilot-2026-super-secure-key"
    _DEFAULT_JWT_SECRET_KEY = "testpilot-jwt-secret"
    
    # 从环境变量读取，如果未设置则使用默认值
    SECRET_KEY = os.environ.get("SECRET_KEY", _DEFAULT_SECRET_KEY)
    DEBUG = False
    # 请求超时时间（秒）
    REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 10))
    # CORS：生产环境只允许配置的域名（支持逗号分隔多域名，自动去空格）
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5000").split(",") if o.strip()]
    # Redis 连接地址（Celery 异步任务用）
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    # Selenium Grid Hub 地址（UI 远程执行用，空字符串则仅支持本地驱动）
    SELENIUM_GRID_URL = os.environ.get("SELENIUM_GRID_URL", "")
    # 压测明细数据保留天数（30 天前的明细自动清理）
    PERF_DETAIL_RETENTION_DAYS = int(os.environ.get("PERF_DETAIL_RETENTION_DAYS", 30))
    # 数据库配置（使用绝对路径，避免不同工作目录下数据丢失）
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'testpilot.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 配置（登录鉴权）
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEFAULT_JWT_SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)  # Access Token 2小时
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)  # Refresh Token 30天

    @classmethod
    def validate_secrets(cls, is_production: bool = False) -> None:
        """启动时校验密钥强度"""
        _validate_secret_key("SECRET_KEY", cls.SECRET_KEY, is_production)
        _validate_secret_key("JWT_SECRET_KEY", cls.JWT_SECRET_KEY, is_production)

    # AI 模型配置（LM Studio 本地大模型服务，支持通过 .env 覆盖）
    AI_API_BASE = os.environ.get("AI_API_BASE", "http://127.0.0.1:1234")
    AI_MODEL = os.environ.get("AI_MODEL", "qwen3.5-9b")
    # AI 生成提示词配置
    AI_API_PROMPT = """你是资深测试开发，请根据业务场景生成一个 JSON 对象。要求：必须包含 name, method, url, headers, body, expect 这 6 个英文键。示例：{"name": "登录测试", "method": "POST", "url": "/api/login", "headers": {}, "body": {}, "expect": "成功"}场景：{scene}"""
    AI_UI_PROMPT = """你是 UI 自动化专家，请根据业务场景生成一个 JSON 对象。要求：必须包含 name, url, steps 这 3 个英文键。示例：{"name": "登录流程", "url": "http://localhost/login", "steps": "步骤 1；步骤 2"}场景：{scene}"""
    AI_ANALYZE_PROMPT = """你是测试诊断专家，请分析日志生成一个 JSON 对象。要求：必须包含 cause, solution 这 2 个英文键。日志：{log}"""


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
