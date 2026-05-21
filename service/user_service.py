from models import User
from sqlalchemy import func

def check_user_password(username, password):
    # 使用大小写不敏感查询，因为用户名在注册时已转换为小写存储
    if username:
        username_lower = username.strip().lower()
        user = User.query.filter(func.lower(User.username) == username_lower).first()
    else:
        return None
        
    if not user:
        return None
    if user.check_password(password):
        return user
    return None
