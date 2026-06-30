"""Service 层单元测试

覆盖 test_service.py / data_drive.py / parallel.py 的核心函数。
"""
import pytest
from unittest.mock import Mock, patch


class TestMergeRetryResults:
    """_merge_retry_results 合并逻辑测试"""

    def test_all_pass(self):
        from service.test_service import _merge_retry_results
        attempts = [
            {"status": "PASS", "code": 200, "time": 0.5},
        ]
        merged = _merge_retry_results(attempts, 0)
        assert merged["status"] == "PASS"
        assert merged["retried"] == 0

    def test_first_fail_then_pass(self):
        from service.test_service import _merge_retry_results
        attempts = [
            {"status": "FAIL", "code": 400, "time": 0.3},
            {"status": "PASS", "code": 200, "time": 0.5},
        ]
        merged = _merge_retry_results(attempts, 1)
        assert merged["status"] == "FLAKY"
        assert merged["retried"] == 1

    def test_all_fail(self):
        from service.test_service import _merge_retry_results
        attempts = [
            {"status": "FAIL", "code": 400, "time": 0.3},
            {"status": "FAIL", "code": 500, "time": 0.4},
        ]
        merged = _merge_retry_results(attempts, 1)
        assert merged["status"] == "FAIL"
        assert merged["retried"] == 1

    def test_all_error(self):
        from service.test_service import _merge_retry_results
        attempts = [
            {"status": "ERROR", "time": 0.1, "error": "timeout"},
            {"status": "ERROR", "time": 0.2, "error": "timeout"},
        ]
        merged = _merge_retry_results(attempts, 1)
        assert merged["status"] == "ERROR"

    def test_retried_but_no_retry_arg(self):
        from service.test_service import _merge_retry_results
        attempts = [
            {"status": "FAIL", "code": 400},
            {"status": "PASS", "code": 200},
        ]
        merged = _merge_retry_results(attempts, 0)
        assert merged["retried"] == 1
        assert merged["status"] == "FLAKY"


class TestDataDriveEngine:
    """数据驱动引擎单元测试"""

    def test_replace_placeholders(self):
        from service.data_drive import _replace_placeholders
        row = {"username": "test1", "pwd": "abc123"}
        assert _replace_placeholders("{{username}}", row) == "test1"
        assert _replace_placeholders("/api/user/{{username}}", row) == "/api/user/test1"
        assert _replace_placeholders("{{unknown}}", row) == "{{unknown}}"

    def test_replace_in_dict_nested(self):
        from service.data_drive import _replace_in_dict
        row = {"name": "alice", "age": "25"}
        d = {"url": "/api/{{name}}", "body": {"user": "{{name}}", "info": "age_{{age}}"}}
        result = _replace_in_dict(d, row)
        assert result["url"] == "/api/alice"
        assert result["body"]["user"] == "alice"
        assert result["body"]["info"] == "age_25"

    def test_replace_empty_row(self):
        from service.data_drive import _replace_placeholders
        assert _replace_placeholders("/api/user/{{username}}", {}) == "/api/user/{{username}}"

    def test_replace_none_value_skipped(self):
        from service.data_drive import _replace_placeholders
        row = {"username": None}
        result = _replace_placeholders("/api/user/{{username}}", row)
        assert result == "/api/user/{{username}}"


class TestSplitIds:
    """split_ids 拆分逻辑测试"""

    def test_exact(self):
        from service.parallel import split_ids
        ids = [1, 2, 3, 4]
        result = split_ids(ids, 2)
        assert len(result) == 2
        assert result[0] == [1, 2]

    def test_uneven(self):
        from service.parallel import split_ids
        ids = [1, 2, 3, 4, 5]
        result = split_ids(ids, 3)
        assert len(result) == 3
        assert sum(len(s) for s in result) == 5

    def test_empty(self):
        from service.parallel import split_ids
        assert split_ids([], 4) == []


class TestParseUpload:
    """文件导入解析测试"""

    def test_json(self):
        from service.data_drive import parse_upload
        content = '[{"username": "a"}]'
        rows = parse_upload(content, "data.json")
        assert len(rows) == 1

    def test_csv(self):
        from service.data_drive import parse_upload
        content = "username,pwd\na,1\n"
        rows = parse_upload(content, "data.csv")
        assert len(rows) == 1

    def test_unsupported_format(self):
        from service.data_drive import parse_upload
        assert parse_upload("a", "data.xlsx") is None
