"""pytest 测试基础设施

提供 app/client/db 等 fixture，使用 SQLite 内存数据库实现隔离。
"""
import pytest
from app import create_app
from extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """创建测试 Flask 应用实例（session 级别，全局一个）"""
    application = create_app("test")
    application.config.update({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "CACHE_TYPE": "SimpleCache",
    })
    with application.app_context():
        _db.create_all()
        # 预先创建 admin 用户，供所有测试复用
        from models import User
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("123456")
            _db.session.add(admin)
            _db.session.commit()
        yield application
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """测试客户端（function 级别，每个测试独立）"""
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def auth_header(app, client):
    """获取认证头（function 级别，每个测试登录一次，独立 token）"""
    resp = client.post("/api/auth/login", json={
        "username": "admin", "password": "123456",
    })
    token = resp.get_json().get("data", {}).get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
