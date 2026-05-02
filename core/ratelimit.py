"""
简易限流与雪崩防护模块
"""
import time
from functools import wraps
from threading import Lock


class RateLimiter:
    """计数器限流器"""
    
    def __init__(self, max_requests=10, window=1):
        """
        max_requests: 时间窗口内允许的最大请求数
        window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.window = window
        self.requests = []
        self.lock = Lock()
    
    def is_allowed(self):
        """检查是否允许请求"""
        with self.lock:
            now = time.time()
            # 清除过期的请求记录
            self.requests = [t for t in self.requests if now - t < self.window]
            
            if len(self.requests) >= self.max_requests:
                return False
            
            self.requests.append(now)
            return True
    
    def get_remaining(self):
        """获取剩余请求数"""
        with self.lock:
            now = time.time()
            self.requests = [t for t in self.requests if now - t < self.window]
            return max(0, self.max_requests - len(self.requests))


class CircuitBreaker:
    """熔断器 - 连续失败后暂时停止服务"""
    
    def __init__(self, failure_threshold=5, recovery_time=60):
        """
        failure_threshold: 连续失败多少次后熔断
        recovery_time: 熔断后多长时间恢复（秒）
        """
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self.lock = Lock()
    
    def is_allowed(self):
        """检查是否允许请求"""
        with self.lock:
            if not self.is_open:
                return True
            
            # 检查是否恢复
            if time.time() - self.last_failure_time > self.recovery_time:
                self.is_open = False
                self.failure_count = 0
                return True
            
            return False
    
    def record_success(self):
        """记录成功"""
        with self.lock:
            self.failure_count = 0
            if self.is_open:
                self.is_open = False
    
    def record_failure(self):
        """记录失败"""
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                self.last_failure_time = time.time()


# 全局限流器实例
# 1分钟允许60次请求
global_limiter = RateLimiter(max_requests=60, window=60)

# 全局熔断器实例
# 连续5次失败后熔断60秒
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
    return wrapper