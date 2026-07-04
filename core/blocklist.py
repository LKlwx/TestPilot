"""JWT Token 黑名单 + 登录防暴力破解（Phase 2.1 已迁至 Redis，懒加载连接）"""

import redis

from config import Config

_redis_client = None

BLOCKLIST_KEY = "jwt:blocklist"
BLOCKLIST_TTL = 7200  # 2 小时

LOGIN_ATTEMPTS_PREFIX = "login:attempts:"
LOGIN_LOCK_TTL = 900  # 15 分钟


def _get_redis():
    """懒加载 Redis 连接，任何异常时降级为内存 dict"""
    from flask import current_app

    try:
        if current_app.config.get("TESTING"):
            return _get_test_store()
    except Exception:
        pass
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(Config.REDIS_URL)
            _redis_client.ping()
        except Exception:
            return _get_test_store()
    return _redis_client


_test_store = {}


def _get_test_store():
    """测试模式：内存 dict 替代 Redis"""
    return _MemoryRedis()


class _MemoryRedis:
    def setex(self, key, ttl, value):
        _test_store[key] = value

    def exists(self, key):
        return key in _test_store

    def get(self, key):
        return _test_store.get(key)

    def incr(self, key):
        _test_store[key] = _test_store.get(key, 0) + 1
        return _test_store[key]

    def expire(self, key, ttl):
        pass

    def delete(self, key):
        _test_store.pop(key, None)


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
