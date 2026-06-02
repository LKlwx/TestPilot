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
