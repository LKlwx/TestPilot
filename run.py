import os
from dotenv import load_dotenv
from app import create_app
from extensions import db
from models import User, TestCase

# 加载 .env 文件（如果存在），使 os.environ.get() 能读取到配置值
load_dotenv()

# 从环境变量读取配置，默认development
env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

# 配置日志系统
from core.logger import setup_logger, log_error
setup_logger(app)


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
