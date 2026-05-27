"""JWT Token 黑名单 + 登录防暴力破解（2.1换 Redis）"""

import time

_blocklist = set()
_login_attempts = {}


def add_to_blocklist(jti: str) -> None:
    _blocklist.add(jti)


def is_blocklisted(jti: str) -> bool:
    return jti in _blocklist


def record_login_failure(username: str) -> int:
    """记录登录失败，返回连续失败次数"""
    now = time.time()
    if username not in _login_attempts:
        _login_attempts[username] = []
    attempts = _login_attempts[username]
    attempts.append(now)
    return len(attempts)


def is_login_locked(username: str) -> bool:
    """检查账号是否被锁定（连续失败5次后锁定15分钟）"""
    if username not in _login_attempts:
        return False
    now = time.time()
    attempts = [t for t in _login_attempts[username] if now - t < 900]
    _login_attempts[username] = attempts
    return len(attempts) >= 5


def reset_login_attempts(username: str) -> None:
    """登录成功后重置失败记录"""
    _login_attempts.pop(username, None)
