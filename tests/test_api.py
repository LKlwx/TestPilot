"""API 层集成测试

使用 conftest 的 client + auth_header fixture 测试核心 API。
"""
import json


class TestAuthAPI:
    """登录/注册 API"""

    def test_register(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "newuser", "password": "Abc12345", "confirm_password": "Abc12345",
        })
        assert resp.status_code == 200
        assert resp.json.get("code") == 200

    def test_register_password_mismatch(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "test2", "password": "Abc12345", "confirm_password": "Def67890",
        })
        assert resp.json.get("code") != 200

    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin", "password": "123456",
        })
        data = resp.get_json()
        assert data is not None
        assert data.get("code") == 200
        assert "access_token" in (data.get("data") or {})

    def test_login_bad_password(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin", "password": "wrongpass",
        })
        assert resp.json.get("code") != 200


class TestTestCaseAPI:
    """接口用例 CRUD + 执行"""

    def test_create_case(self, client, auth_header):
        resp = client.post("/api/test/case", json={
            "name": "测试用例", "method": "GET", "url": "http://example.com",
            "headers": "{}", "body": "{}",
        }, headers=auth_header)
        assert resp.status_code == 200
        assert resp.json.get("data", {}).get("id") > 0

    def test_list_cases(self, client, auth_header):
        resp = client.get("/api/test/cases", headers=auth_header)
        assert resp.status_code == 200
        assert "list" in resp.json.get("data", {})

    def test_execute_case(self, client, auth_header):
        # 先创建
        create = client.post("/api/test/case", json={
            "name": "执行测试", "method": "GET", "url": "http://example.com",
            "headers": "{}", "body": "{}",
        }, headers=auth_header)
        cid = create.json["data"]["id"]
        # 执行
        resp = client.post(f"/api/test/case/{cid}/run", json={}, headers=auth_header)
        assert resp.status_code == 200

    def test_delete_case(self, client, auth_header):
        create = client.post("/api/test/case", json={
            "name": "删除测试", "method": "GET", "url": "http://example.com",
        }, headers=auth_header)
        cid = create.json["data"]["id"]
        resp = client.delete(f"/api/test/case/{cid}", headers=auth_header)
        assert resp.status_code == 200


class TestDashboardAPI:
    """Dashboard 统计接口"""

    def test_dashboard_data(self, client, auth_header):
        resp = client.get("/api/auth/dashboard/data", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json.get("data", {})
        assert "api_case" in data
        assert "total_case" in data


class TestEnvAPI:
    """环境管理 API"""

    def test_create_env(self, client, auth_header):
        resp = client.post("/api/env/add", json={
            "name": "测试环境", "base_url": "http://test.com",
            "headers": "{}", "variables": "{}", "is_default": False,
        }, headers=auth_header)
        assert resp.status_code == 200

    def test_list_envs(self, client, auth_header):
        resp = client.get("/api/env/list", headers=auth_header)
        assert resp.status_code == 200
        assert "list" in resp.json.get("data", {})


class TestSuiteAPI:
    """套件管理 API"""

    def test_create_and_run_suite(self, client, auth_header):
        # 创建套件
        resp = client.post("/api/suite/add", json={
            "name": "测试套件", "description": "", "cases": [],
        }, headers=auth_header)
        assert resp.status_code == 200
        sid = resp.json["data"]["id"]
        # 执行空套件
        resp = client.post(f"/api/suite/{sid}/run", json={}, headers=auth_header)
        assert resp.status_code == 200

    def test_list_suites(self, client, auth_header):
        resp = client.get("/api/suite/list", headers=auth_header)
        assert resp.status_code == 200


class TestSchedulerAPI:
    """定时任务 API"""

    def test_create_task(self, client, auth_header):
        resp = client.post("/api/scheduler/task/add", json={
            "name": "测试定时任务", "cron_expr": "0 3 * * *",
        }, headers=auth_header)
        assert resp.status_code == 200

    def test_list_tasks(self, client, auth_header):
        resp = client.get("/api/scheduler/tasks", headers=auth_header)
        assert resp.status_code == 200


class TestCoverageAPI:
    """覆盖率 + 契约 API"""

    def test_static_pages(self, client, auth_header):
        resp = client.get("/api/env/page", headers=auth_header)
        assert resp.status_code == 200

    def test_contracts(self, client, auth_header):
        resp = client.get("/api/coverage/contracts", headers=auth_header)
        assert resp.status_code == 200
