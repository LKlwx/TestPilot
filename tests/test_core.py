"""
TestPilot 核心功能测试
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import allure
from app import create_app
from models import User, TestCase, TestReport
from core.exception import APIException, NotFoundException
from core.response import success, error
from core.execution_context import ExecutionContext, RecursiveVariableError
from core.assert_engine import AssertEngine
from core.http_client import HTTPResponse, BaseHTTPClient
from unittest.mock import MagicMock


@allure.feature("核心模块")
@allure.story("应用初始化")
def test_app_creation():
    app = create_app()
    assert app is not None


def test_models_import():
    assert User is not None
    assert TestCase is not None
    assert TestReport is not None


def test_exception_import():
    assert APIException is not None
    assert NotFoundException is not None


def test_response_import():
    assert success is not None
    assert error is not None


# ========== ExecutionContext 单元测试 ==========

@allure.feature("ExecutionContext")
@allure.story("循环引用保护")
def test_execution_context_recursive_limit():
    ctx = ExecutionContext()
    ctx.set_var("a", "${b}")
    ctx.set_var("b", "${a}")
    try:
        ctx.replace_placeholders("${a}")
        assert False, "应该抛出 RecursiveVariableError"
    except RecursiveVariableError:
        pass


def test_execution_context_replace_none_text():
    ctx = ExecutionContext()
    assert ctx.replace_placeholders(None) is None
    assert ctx.replace_placeholders("") == ""


def test_execution_context_independence():
    ctx1 = ExecutionContext()
    ctx2 = ExecutionContext()
    ctx1.set_var("token", "ctx1_token")
    ctx2.set_var("token", "ctx2_token")
    assert ctx1.get_var("token") == "ctx1_token"
    assert ctx2.get_var("token") == "ctx2_token"


def test_execution_context_add_log():
    ctx = ExecutionContext()
    ctx.add_log("started")
    ctx.add_log("completed")
    assert len(ctx.logs) == 2
    assert ctx.logs[0] == "started"
    assert ctx.logs[1] == "completed"


# ========== AssertEngine 单元测试 ==========

class MockResponse:
    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = status_code
        self._json_data = json_data or {}
    def json(self):
        return self._json_data


@allure.feature("AssertEngine")
@allure.story("包含断言")
def test_assert_contains_pass():
    with allure.step("创建 Mock 响应"):
        resp = MockResponse(text="hello world")
    with allure.step("执行包含断言"):
        e = AssertEngine(resp)
        passed, msg = e.execute("hello")
    assert passed is True
    with allure.step("验证断言结果"):
        assert passed is True


def test_assert_contains_fail():
    resp = MockResponse(text="hello world")
    e = AssertEngine(resp)
    passed, msg = e.execute("bye")
    assert passed is False


def test_assert_status_code():
    resp = MockResponse(status_code=200)
    e = AssertEngine(resp)
    assert e.execute("status == 200")[0] is True
    assert e.execute("status == 404")[0] is False
    assert e.execute("status != 404")[0] is True
    assert e.execute("status != 200")[0] is False


def test_assert_json_path():
    resp = MockResponse(json_data={"data": {"token": "abc123"}})
    e = AssertEngine(resp)
    assert e.execute("$.data.token == abc123")[0] is True
    assert e.execute("$.data.token == xyz")[0] is False
    assert e.execute("$.data.token != xyz")[0] is True


def test_assert_regex():
    resp = MockResponse(text="order-2026-05-30-001")
    e = AssertEngine(resp)
    assert e.execute("match ^order-\\d{4}-\\d{2}")[0] is True
    assert e.execute("match ^order-\\d{3}-")[0] is False


def test_assert_time():
    resp = MockResponse()
    e = AssertEngine(resp, cost_time=0.5)
    assert e.execute("time < 1000")[0] is True
    assert e.execute("time > 1000")[0] is False
    assert e.execute("time > 400")[0] is True


# ========== BaseHTTPClient 单元测试 ==========

@allure.feature("BaseHTTPClient")
class MockRequestsResponse:
    """模拟 requests.Response"""
    def __init__(self, status_code=200, text="ok", headers=None, json_data=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"Content-Type": "application/json"}
        self._json = json_data
    def json(self):
        return self._json or {"data": {"token": "abc"}}


def test_http_response_validate_status():
    r = HTTPResponse(MockRequestsResponse(status_code=200))
    r.validate_status(200)
    assert r._passed is True

    r2 = HTTPResponse(MockRequestsResponse(status_code=404))
    r2.validate_status(200)
    try:
        r2.done()
        assert False, "应抛出 AssertionError"
    except AssertionError:
        pass


def test_http_response_validate_json():
    r = HTTPResponse(MockRequestsResponse(json_data={"data": {"id": 42}}))
    r.validate_json("$.data.id", 42).done()
    assert r._passed is True


def test_http_response_validate_header():
    r = HTTPResponse(MockRequestsResponse(headers={"Content-Type": "application/json"}))
    r.validate_header("Content-Type", "application/json").done()
    assert r._passed is True


def test_http_response_validate_regex():
    r = HTTPResponse(MockRequestsResponse(text="order-2026-05-30-001"))
    r.validate_regex(r"\d{4}-\d{2}-\d{2}").done()
    assert r._passed is True


def test_http_response_chain_all():
    """测试完整链式调用"""
    with allure.step("创建 mock 响应"):
        r = HTTPResponse(MockRequestsResponse(status_code=200, text="success", json_data={"token": "abc"}))
    with allure.step("链式断言：状态码 + JSONPath + Header + 正则"):
        r.validate_status(200).validate_json("$.token", "abc").validate_header("Content-Type", "application/json").validate_regex("success").done()
    assert r._passed is True


# ========== BasePage 单元测试 ==========

@allure.feature("BasePage")
def test_by_map_contains_all_locators():
    from core.base_page import BY_MAP
    for k in ["id", "name", "xpath", "css", "linkText", "className"]:
        assert k in BY_MAP, f"缺少定位方式: {k}"


def test_by_map_invalid_returns_xpath():
    from core.base_page import BY_MAP
    from selenium.webdriver.common.by import By
    assert BY_MAP.get("invalid", By.XPATH) == By.XPATH


def test_base_page_create():
    from selenium.webdriver.support.ui import WebDriverWait
    mock_driver = MagicMock()
    from core.base_page import BasePage
    bp = BasePage(mock_driver, timeout=5)
    assert bp.driver is mock_driver
    assert isinstance(bp.wait, WebDriverWait)


# ========== DataFactory 单元测试 ==========

@allure.feature("DataFactory")
def test_data_factory_username():
    from core.data_factory import DataFactory
    u1 = DataFactory.username()
    u2 = DataFactory.username()
    assert u1 and u2
    assert u1 != u2


def test_data_factory_email():
    from core.data_factory import DataFactory
    e = DataFactory.email()
    assert "@" in e


def test_data_factory_phone():
    from core.data_factory import DataFactory
    p = DataFactory.phone()
    digits = p.replace("-", "").replace(" ", "")
    assert digits.isdigit()


def test_data_factory_password_meets_requirements():
    from core.data_factory import DataFactory
    pw = DataFactory.password()
    assert len(pw) >= 8
    assert any(c.isalpha() for c in pw)
    assert any(c.isdigit() for c in pw)


# ========== DataPool 单元测试 ==========

@allure.feature("DataPool")
def test_data_pool_get_or_create():
    from core.data_pool import DataPool
    pool = DataPool()
    called = 0

    def factory():
        nonlocal called
        called += 1
        return "value"

    assert pool.get_or_create("key", factory) == "value"
    assert called == 1
    # 第二次调用不再走 factory
    assert pool.get_or_create("key", factory) == "value"
    assert called == 1


def test_data_pool_clear():
    from core.data_pool import DataPool
    pool = DataPool()
    pool.set("a", 1)
    pool.set("b", 2)
    pool.clear()
    assert pool.get("a") is None
    assert pool.get("b") is None


def test_data_pool_set_override():
    from core.data_pool import DataPool
    pool = DataPool()
    pool.set("k", "old")
    pool.set("k", "new")
    assert pool.get("k") == "new"


# ========== 数据驱动测试 单元测试 ==========

@allure.feature("DataDrive")
def test_replace_placeholders():
    from service.data_drive import _replace_placeholders
    row = {"username": "test1", "pwd": "abc123"}
    assert _replace_placeholders("{{username}}", row) == "test1"
    assert _replace_placeholders("/api/user/{{username}}", row) == "/api/user/test1"
    assert _replace_placeholders("{{unknown}}", row) == "{{unknown}}"


def test_replace_in_dict():
    from service.data_drive import _replace_in_dict
    row = {"name": "alice", "age": "25"}
    d = {"url": "/api/{{name}}", "body": {"user": "{{name}}", "info": "age_{{age}}"}}
    result = _replace_in_dict(d, row)
    assert result["url"] == "/api/alice"
    assert result["body"]["user"] == "alice"
    assert result["body"]["info"] == "age_25"


def test_parse_upload_json():
    from service.data_drive import parse_upload
    content = '[{"username": "a", "pwd": "1"}, {"username": "b", "pwd": "2"}]'
    rows = parse_upload(content, "data.json")
    assert len(rows) == 2
    assert rows[0]["username"] == "a"


def test_parse_upload_csv():
    from service.data_drive import parse_upload
    content = "username,pwd\na,1\nb,2\n"
    rows = parse_upload(content, "data.csv")
    assert len(rows) == 2
    assert rows[0]["username"] == "a"


# ========== 契约测试 单元测试 ==========

@allure.feature("ApiContract")
def test_validate_schema_pass():
    from core.assert_engine import AssertEngine
    engine = AssertEngine(response=None)
    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
        "required": ["id"],
    }
    data = {"id": 1, "name": "test"}
    passed, msg = engine.validate_schema(data, schema)
    assert passed


def test_validate_schema_type_mismatch():
    from core.assert_engine import AssertEngine
    engine = AssertEngine(response=None)
    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}},
    }
    data = {"id": "not_int"}
    passed, msg = engine.validate_schema(data, schema)
    assert not passed
    assert "integer" in msg


def test_validate_schema_missing_required():
    from core.assert_engine import AssertEngine
    engine = AssertEngine(response=None)
    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
        "required": ["name"],
    }
    data = {"id": 1}
    passed, msg = engine.validate_schema(data, schema)
    assert not passed
    assert "name" in msg or "required" in msg


def test_validate_schema_no_schema():
    from core.assert_engine import AssertEngine
    engine = AssertEngine(response=None)
    passed, msg = engine.validate_schema({"a": 1}, None)
    assert passed


@allure.feature("SwaggerParser")
def test_resolve_schema_refs():
    from api.coverage import _resolve_schema_refs
    schemas = {
        "User": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
        },
    }
    resolved = _resolve_schema_refs({"$ref": "#/components/schemas/User"}, schemas)
    assert resolved["type"] == "object"
    assert resolved["properties"]["id"]["type"] == "integer"


# ========== 导入导出 单元测试 ==========

@allure.feature("ImportExport")
def test_schema_to_example_object():
    from api.coverage import _schema_to_example
    schema = {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "age": {"type": "integer"},
        },
    }
    result = _schema_to_example(schema)
    assert result["username"] == "string"
    assert result["age"] == 0


def test_schema_to_example_nested():
    from api.coverage import _schema_to_example
    schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }
    result = _schema_to_example(schema)
    assert result["user"]["id"] == 0
    assert result["user"]["name"] == "string"
    assert result["tags"] == ["string"]


# ========== 分布式并行 单元测试 ==========

@allure.feature("Parallel")
def test_split_ids_exact():
    from service.parallel import split_ids
    ids = [1, 2, 3, 4]
    split = split_ids(ids, 2)
    assert len(split) == 2
    assert split[0] == [1, 2]
    assert split[1] == [3, 4]


def test_split_ids_uneven():
    from service.parallel import split_ids
    ids = [1, 2, 3, 4, 5]
    split = split_ids(ids, 3)
    assert len(split) == 3
    assert sum(len(s) for s in split) == 5


def test_split_ids_more_chunks_than_items():
    from service.parallel import split_ids
    ids = [1, 2]
    split = split_ids(ids, 5)
    assert len(split) == 2
    assert split[0] == [1]


def test_split_ids_empty():
    from service.parallel import split_ids
    assert split_ids([], 4) == []


def test_split_ids_zero_workers():
    from service.parallel import split_ids
    ids = [1, 2, 3]
    assert split_ids(ids, 0) == [ids]
