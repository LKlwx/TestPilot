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