"""数据池：跨用例共享预热数据

    pool = DataPool()
    token = pool.get_or_create("login_token", lambda: login_and_get_token())
    # 用例 A 调用 → 触发登录 → 存入池
    # 用例 B 调用 → 直接复用

支持与 ExecutionContext 配合使用：
    context.set_var("token", pool.get_or_create("login_token", fetch_fn))
"""

import threading


class DataPool:
    """线程安全的跨用例数据共享池

    作用域：单次执行上下文中所有用例共享。
    典型场景：多个用例共用同一个登录 token，避免每个用例重复登录。
    """

    def __init__(self):
        self._pool = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str, factory_fn, *args, **kwargs):
        """获取或创建共享数据

        Args:
            key: 数据池键名，如 "login_token"
            factory_fn: 数据不存在时调用此函数创建
            args, kwargs: 透传给 factory_fn

        Returns:
            共享数据对象（str / dict / 任意类型）
        """
        if key in self._pool:
            return self._pool[key]

        with self._lock:
            if key in self._pool:
                return self._pool[key]
            value = factory_fn(*args, **kwargs)
            self._pool[key] = value
            return value

    def set(self, key: str, value):
        """显式设置池中数据（覆盖已有值）"""
        with self._lock:
            self._pool[key] = value

    def get(self, key: str, default=None):
        """读取池中数据，不存在返回 default"""
        return self._pool.get(key, default)

    def clear(self):
        """清空数据池（用例批次结束时调用）"""
        with self._lock:
            self._pool.clear()
