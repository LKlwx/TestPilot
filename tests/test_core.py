"""
TestPilot 核心功能测试
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import User, TestCase, TestReport
from core.exception import APIException, NotFoundException
from core.response import success, error
from core.execution_context import ExecutionContext, RecursiveVariableError
from core.assert_engine import AssertEngine


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

def test_execution_context_create():
    ctx = ExecutionContext()
    assert ctx.execution_id is not None
    assert ctx.vars == {}
    assert ctx.logs == []


def test_execution_context_set_get():
    ctx = ExecutionContext()
    ctx.set_var("token", "abc123")
    assert ctx.get_var("token") == "abc123"
    assert ctx.get_var("nonexistent") is None
    assert ctx.get_var("nonexistent", "default") == "default"


def test_execution_context_replace_basic():
    ctx = ExecutionContext()
    ctx.set_var("token", "abc123")
    result = ctx.replace_placeholders("Bearer ${token}")
    assert result == "Bearer abc123"


def test_execution_context_replace_multiple():
    ctx = ExecutionContext()
    ctx.set_var("token", "abc")
    ctx.set_var("id", "42")
    result = ctx.replace_placeholders("/api/user/${id}?token=${token}")
    assert result == "/api/user/42?token=abc"


def test_execution_context_replace_no_match():
    ctx = ExecutionContext()
    ctx.set_var("token", "abc")
    result = ctx.replace_placeholders("/api/user/1")
    assert result == "/api/user/1"


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


def test_assert_contains_pass():
    resp = MockResponse(text="hello world")
    e = AssertEngine(resp)
    passed, msg = e.execute("hello")
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