from functools import wraps

from flask_jwt_extended import get_jwt_identity, jwt_required

from core.exception import AuthException


def require_role(roles: list):
    """路由权限校验装饰器

    封装JWT鉴权+角色校验。
    自动带@jwt_required()。

    用法:
        @require_role(["admin"])             # 仅管理员
        @require_role(["admin", "tester"])    # 管理员和测试员
    """

    def decorator(f):
        @wraps(f)
        @jwt_required()
        def wrapper(*args, **kwargs):
            from models import User

            identity = get_jwt_identity()
            user = User.query.get(int(identity))
            if not user or user.role not in roles:
                raise AuthException("权限不足")
            return f(*args, **kwargs)

        return wrapper

    return decorator
