"""
简易限流与雪崩防护模块
"""
import time
import uuid
from functools import wraps
from threading import Lock


class RateLimiter:
    """单 key 滑动窗口限流器"""

    def __init__(self, max_requests=10, window=1):
        self.max_requests = max_requests
        self.window = window
        self.requests = []
        self.lock = Lock()

    def is_allowed(self):
        with self.lock:
            now = time.time()
            self.requests = [t for t in self.requests if now - t < self.window]
            if len(self.requests) >= self.max_requests:
                return False
            self.requests.append(now)
            return True

    def get_remaining(self):
        with self.lock:
            now = time.time()
            self.requests = [t for t in self.requests if now - t < self.window]
            return max(0, self.max_requests - len(self.requests))


class RedisSlidingWindowLimiter:
    """基于 Redis 有序集合的滑动窗口限流器

    每个 key 一个 Sorted Set，score = 时间戳。
    自动过期清理，不占内存；多 Worker 共享同一 Redis，分布式一致。
    """

    def __init__(self):
        self._redis_client = None

    def _get_redis(self):
        if self._redis_client is None:
            import redis as redis_lib
            from config import Config
            self._redis_client = redis_lib.from_url(Config.REDIS_URL)
        return self._redis_client

    def is_allowed(self, key, max_requests, window):
        r = self._get_redis()
        now = time.time()

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, "-inf", now - window)
        pipe.zcard(key)
        results = pipe.execute()
        count = results[1]

        if count >= max_requests:
            if count == 0:
                r.delete(key)
            return False

        member = f"{now}:{uuid.uuid4().hex}"
        r.zadd(key, {member: now})
        r.expire(key, window + 60)
        return True


class CircuitBreaker:
    """熔断器 - 连续失败后暂时停止服务"""

    def __init__(self, failure_threshold=5, recovery_time=60):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self.lock = Lock()

    def is_allowed(self):
        with self.lock:
            if not self.is_open:
                return True
            if time.time() - self.last_failure_time > self.recovery_time:
                self.is_open = False
                self.failure_count = 0
                return True
            return False

    def record_success(self):
        with self.lock:
            self.failure_count = 0
            if self.is_open:
                self.is_open = False

    def record_failure(self):
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                self.last_failure_time = time.time()


# 全局限流器实例（10 req/sec 兜底）
global_limiter = RateLimiter(max_requests=600, window=60)

# Redis 滑动窗口限流器（多 Worker 共享、自动过期）
tiered_limiter = RedisSlidingWindowLimiter()

# 全局熔断器实例（连续5次失败后熔断60秒）
global_circuit = CircuitBreaker(failure_threshold=5, recovery_time=60)


def rate_limit(max_requests=60, window=60):
    """限流装饰器"""
    limiter = RateLimiter(max_requests=max_requests, window=window)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not limiter.is_allowed():
                return {"code": 429, "msg": "请求过于频繁，请稍后再试"}, 429
            return func(*args, **kwargs)
        return wrapper
    return decorator


def circuit_protect(failure_threshold=3, recovery_time=30):
    """熔断保护装饰器"""
    breaker = CircuitBreaker(failure_threshold=failure_threshold, recovery_time=recovery_time)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not breaker.is_allowed():
                return {"code": 503, "msg": "服务暂不可用，请稍后再试"}, 503
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        return wrapper
    return decorator
