from app import create_app
from extensions import db
from models import User, TestCase

# 初始化应用
app = create_app("development")

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

        # 预置3个真实API测试用例（检查特定用例名是否存在）
        demo_names = ["豆瓣图书搜索", "GitHub用户信息", "心知天气查询"]
        existing_names = [c.name for c in TestCase.query.filter(TestCase.name.in_(demo_names)).all()]

        cases = []
        for name in demo_names:
            if name not in existing_names:
                if name == "豆瓣图书搜索":
                    cases.append({"name": name, "method": "GET", "url": "https://api.douban.com/v2/book/search", "headers": "{}", "body": "{\"q\": \"python\", \"count\": 1}", "expect": "python"})
                elif name == "GitHub用户信息":
                    cases.append({"name": name, "method": "GET", "url": "https://api.github.com/users/octocat", "headers": "{}", "body": "{}", "expect": "octocat"})
                elif name == "心知天气查询":
                    cases.append({"name": name, "method": "GET", "url": "https://api.seniverse.com/v4/weather/now", "headers": "{}", "body": "{\"location\": \"beijing\"}", "expect": "now"})

        if cases:
            for c in cases:
                case = TestCase(
                    name=c["name"],
                    method=c["method"],
                    url=c["url"],
                    headers=c["headers"],
                    body=c["body"],
                    expect=c["expect"]
                )
                db.session.add(case)
            db.session.commit()
            print(f"Success: {len(cases)} demo cases added.")


if __name__ == "__main__":
    init_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
