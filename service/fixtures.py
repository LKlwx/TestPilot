"""测试数据预置与清理

提供上下文管理器风格的 Setup/Teardown：

    from service.fixtures import test_user

    with test_user() as user:
        # 用户已插入数据库，后置清理由 __exit__ 保证
        case.url = f"/api/user/{user.id}"
        ...
        # 出 with 块后用户自动删除

支持数据覆盖：
    with test_user(username="admin_test") as user:
        ...
"""
from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError
from models import User, TestCase
from extensions import db
from core.data_factory import DataFactory
from core.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def test_user(username=None, role="tester"):
    """创建临时用户 → yield → 自动清理

    Args:
        username: 指定用户名（可选），不传则 DataFactory 随机生成
        role: 用户角色，默认 tester

    Yields:
        User 实例（已持久化到数据库）
    """
    username = username or DataFactory.username()
    user = User(
        username=username,
        password_hash="",  # 临时用户不做密码验证
        role=role,
    )
    db.session.add(user)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    try:
        yield user
    finally:
        try:
            db.session.delete(user)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            logger.error("temp user cleanup failed: user=%s", username)
        except Exception as e:
            db.session.rollback()
            logger.error("temp user cleanup unexpected: user=%s, error=%s", username, str(e))
