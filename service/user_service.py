from sqlalchemy import func

from core.logger import get_logger
from models import User

logger = get_logger(__name__)


def check_user_password(username, password):
    if username:
        username_lower = username.strip().lower()
        user = User.query.filter(func.lower(User.username) == username_lower).first()
    else:
        return None

    if not user:
        logger.warning("登录失败: 用户不存在 (username=%s)", username)
        return None
    if user.check_password(password):
        logger.info("登录成功: user_id=%d, username=%s", user.id, user.username)
        return user
    logger.warning("登录失败: 密码错误 (user_id=%d, username=%s)", user.id, user.username)
    return None
