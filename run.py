import os
from dotenv import load_dotenv
# 必须在 create_app 导入前加载 .env，否则 Config 类属性求值时读不到
load_dotenv()
from app import create_app
from extensions import db
from models import User, TestCase


# 从环境变量读取配置，默认development
env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

# 配置日志系统
from core.logger import setup_logger, log_error
setup_logger(app)


def init_admin():
    """自动初始化超级管理员（先执行迁移，再创建 admin 用户）"""
    with app.app_context():
        from flask_migrate import upgrade
        upgrade()
        # 检查是否已存在 admin 用户
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("123456")
            db.session.add(admin)
            db.session.commit()
            import logging
            logging.info("Success: Default admin created.")

if __name__ == "__main__":
    init_admin()
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False), threaded=True)
