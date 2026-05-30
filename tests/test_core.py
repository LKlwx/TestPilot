"""
TestPilot 核心功能测试
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_app_creation():
    """测试 Flask 应用能否成功创建"""
    from app import create_app
    app = create_app()
    assert app is not None


def test_models_import():
    """测试模型导入"""
    from models import User, TestCase, TestReport
    assert User is not None
    assert TestCase is not None
    assert TestReport is not None


def test_exception_import():
    """测试异常导入"""
    from core.exception import APIException, NotFoundException
    assert APIException is not None
    assert NotFoundException is not None


def test_response_import():
    """测试响应导入"""
    from core.response import success, error
    assert success is not None
    assert error is not None


# ========== ExecutionContext 单元测试 ==========

def test_execution_context_create():
    """测试 ExecutionContext 创建"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    assert ctx.execution_id is not None
    assert ctx.vars == {}
    assert ctx.logs == []


def test_execution_context_set_get():
    """测试变量存入和读取"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    ctx.set_var("token", "abc123")
    assert ctx.get_var("token") == "abc123"
    assert ctx.get_var("nonexistent") is None
    assert ctx.get_var("nonexistent", "default") == "default"


def test_execution_context_replace_basic():
    """测试变量替换"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    ctx.set_var("token", "abc123")
    result = ctx.replace_placeholders("Bearer ${token}")
    assert result == "Bearer abc123"


def test_execution_context_replace_multiple():
    """测试多变量替换"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    ctx.set_var("token", "abc")
    ctx.set_var("id", "42")
    result = ctx.replace_placeholders("/api/user/${id}?token=${token}")
    assert result == "/api/user/42?token=abc"


def test_execution_context_replace_no_match():
    """测试无匹配占位符时原文不变"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    ctx.set_var("token", "abc")
    result = ctx.replace_placeholders("/api/user/1")
    assert result == "/api/user/1"


def test_execution_context_recursive_limit():
    """测试循环引用触发深度上限"""
    from core.execution_context import ExecutionContext, RecursiveVariableError
    ctx = ExecutionContext()
    ctx.set_var("a", "${b}")
    ctx.set_var("b", "${a}")
    try:
        ctx.replace_placeholders("${a}")
        assert False, "应该抛出 RecursiveVariableError"
    except RecursiveVariableError:
        pass


def test_execution_context_replace_none_text():
    """测试传入 None/空 不报错"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    assert ctx.replace_placeholders(None) is None
    assert ctx.replace_placeholders("") == ""


def test_execution_context_independence():
    """测试多个 ExecutionContext 独立，变量不互串"""
    from core.execution_context import ExecutionContext
    ctx1 = ExecutionContext()
    ctx2 = ExecutionContext()
    ctx1.set_var("token", "ctx1_token")
    ctx2.set_var("token", "ctx2_token")
    assert ctx1.get_var("token") == "ctx1_token"
    assert ctx2.get_var("token") == "ctx2_token"


def test_execution_context_add_log():
    """测试日志记录"""
    from core.execution_context import ExecutionContext
    ctx = ExecutionContext()
    ctx.add_log("started")
    ctx.add_log("completed")
    assert len(ctx.logs) == 2
    assert ctx.logs[0] == "started"
    assert ctx.logs[1] == "completed"