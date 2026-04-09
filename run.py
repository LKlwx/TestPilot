from app import create_app
from extensions import db
from models import User

# 初始化应用
app = create_app("development")


def init_admin():
    """自动初始化超级管理员"""
    with app.app_context():
        db.create_all()
        # 检查是否已存在 admin 用户
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("123456")
            db.session.add(admin)
            db.session.commit()
            print("Success: Default admin created.")


if __name__ == "__main__":
    init_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
