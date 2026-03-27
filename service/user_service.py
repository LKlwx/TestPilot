from models import User

def check_user_password(username, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        return None
    if user.check_password(password):
        return user
    return None
