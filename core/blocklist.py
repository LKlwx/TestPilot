"""JWT Token 黑名单 + 登录防暴力破解（Phase 2.1 已迁至 Redis，懒加载连接）"""

import redis
from config import Config

_redis_client = None

BLOCKLIST_KEY = "jwt:blocklist"
BLOCKLIST_TTL = 7200  # 2 小时

LOGIN_ATTEMPTS_PREFIX = "login:attempts:"
LOGIN_LOCK_TTL = 900  # 15 分钟


def _get_redis():
    """懒加载 Redis 连接，避免导入时 Redis 未就绪导致启动失败"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(Config.REDIS_URL)
    return _redis_client


def add_to_blocklist(jti: str) -> None:
    r = _get_redis()
    r.setex(f"jwt:blocklist:{jti}", BLOCKLIST_TTL, "1")


def is_blocklisted(jti: str) -> bool:
    r = _get_redis()
    return r.exists(f"jwt:blocklist:{jti}")


def record_login_failure(username: str) -> int:
    key = LOGIN_ATTEMPTS_PREFIX + username
    r = _get_redis()
    count = r.incr(key)
    r.expire(key, LOGIN_LOCK_TTL)
    return count


def is_login_locked(username: str) -> bool:
    key = LOGIN_ATTEMPTS_PREFIX + username
    r = _get_redis()
    count = r.get(key)
    return count is not None and int(count) >= 5


def reset_login_attempts(username: str) -> None:
    r = _get_redis()
    r.delete(LOGIN_ATTEMPTS_PREFIX + username)
