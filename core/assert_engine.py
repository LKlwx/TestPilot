import json
import re

try:
    import jsonschema

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


class AssertEngine:
    """断言引擎：支持多种断言类型的统一执行入口

    支持的断言格式：
        - 包含断言：        expect_keyword              (兼容旧版，纯文本)
        - 状态码断言：      status == 200
        - JSON 路径断言：   $.data.token == expected_value
        - 正则断言：        match ^\\d{4}-\\d{2}-\\d{2}$
        - 响应时间断言：    time < 1000
        - Schema 校验断言：  schema                       (仅用于外部调用 validate_schema)
    """

    def __init__(self, response, cost_time=None):
        self.response = response
        self.cost_time = cost_time

    def execute(self, rule: str) -> tuple:
        """执行单条断言规则，返回 (passed: bool, message: str)"""
        rule = rule.strip()
        if not rule:
            return True, ""

        if rule.startswith("status "):
            return self._assert_status(rule)
        if rule.startswith("$."):
            return self._assert_json_path(rule)
        if rule.startswith("match "):
            return self._assert_regex(rule)
        if rule.startswith("time "):
            return self._assert_time(rule)
        return self._assert_contains(rule)

    def _assert_status(self, rule: str) -> tuple:
        """status == 200  /  status != 404"""
        m = re.match(r"^status\s*([=!]{1,2})\s*(\d+)$", rule)
        if not m:
            return False, f"状态码断言格式错误: {rule}"
        op, expected = m.group(1), int(m.group(2))
        actual = self.response.status_code
        if op == "==":
            passed = actual == expected
        elif op == "!=":
            passed = actual != expected
        else:
            return False, f"不支持的状态码运算符: {op}"
        return (passed, f"状态码断言 {'通过' if passed else '失败'}：期望 {op} {expected}，实际 {actual}")

    def _assert_json_path(self, rule: str) -> tuple:
        """$.data.token == abc"""
        m = re.match(r"^(\$\..+?)\s*([=!]{1,2})\s*(.*)$", rule)
        if not m:
            return False, f"JSON 路径断言格式错误: {rule}"
        path, op, expected = m.group(1), m.group(2), m.group(3)
        expected = expected.strip()

        keys = path.replace("$.", "").split(".")
        try:
            data = self.response.json()
            actual = data
            for k in keys:
                if isinstance(actual, list):
                    actual = actual[int(k)]
                else:
                    actual = actual[k]
            if isinstance(actual, (bool, int, float, type(None))):
                actual = json.dumps(actual)
            else:
                actual = str(actual)
        except Exception:
            return False, f"JSON 路径断言失败：无法从响应中提取 {path}"

        if op == "==":
            passed = actual == expected
        elif op == "!=":
            passed = actual != expected
        else:
            return False, f"不支持的运算符: {op}"
        return (passed, f"JSON 路径断言 {'通过' if passed else '失败'}：{path} {op} {expected}，实际 {actual}")

    def _assert_regex(self, rule: str) -> tuple:
        """match ^\\d{4}-\\d{2}-\\d{2}$"""
        pattern = rule[6:].strip()
        try:
            matched = re.search(pattern, self.response.text)
            passed = bool(matched)
        except re.error as e:
            return False, f"正则表达式错误: {e}"
        return (
            passed,
            f"正则断言 {'通过' if passed else '失败'}：{'匹配成功' if passed else f'未匹配 pattern={pattern}'}",
        )

    def _assert_time(self, rule: str) -> tuple:
        """time < 1000  /  time > 500  /  time <= 2000"""
        m = re.match(r"^time\s*([<>=!]+)\s*(\d+\.?\d*)$", rule)
        if not m:
            return False, f"响应时间断言格式错误: {rule}"
        op, expected_s = m.group(1), float(m.group(2))
        actual = self.cost_time * 1000 if self.cost_time else 0  # cost_time is in seconds, convert to ms
        ops = {
            ">": lambda a, e: a > e,
            "<": lambda a, e: a < e,
            ">=": lambda a, e: a >= e,
            "<=": lambda a, e: a <= e,
            "==": lambda a, e: a == e,
        }
        if op not in ops:
            return False, f"不支持的运算符: {op}"
        passed = ops[op](actual, expected_s)
        return (passed, f"响应时间断言 {'通过' if passed else '失败'}：期望 {op} {expected_s}ms，实际 {actual:.0f}ms")

    def _assert_contains(self, rule: str) -> tuple:
        """包含断言（向后兼容）"""
        passed = rule in self.response.text
        return (passed, f"包含断言 {'通过' if passed else '失败'}：{'包含' if passed else '未包含'}关键字 '{rule}'")

    def validate_schema(self, response_json, schema):
        """校验响应体是否符合 JSON Schema

        Args:
            response_json: 实际的响应体（dict 或 list）
            schema: JSON Schema 定义（dict）

        Returns:
            (passed: bool, message: str)
        """
        if not schema:
            return True, "无契约定义，跳过 Schema 校验"
        if not _HAS_JSONSCHEMA:
            return True, "jsonschema 未安装，跳过 Schema 校验"

        try:
            jsonschema.validate(instance=response_json, schema=schema)
            return True, "Schema 校验通过：响应体符合契约定义"
        except jsonschema.ValidationError as e:
            path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else e.message
            return False, f"Schema 校验失败: {e.message}"
