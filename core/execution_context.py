import uuid
import time
import logging


class RecursiveVariableError(Exception):
    """变量替换超出最大递归深度"""


class ExecutionContext:
    def __init__(self, execution_id: str = None):
        self.execution_id = execution_id or uuid.uuid4().hex
        self.vars = {}
        self.start_time = time.time()
        self.logs = []

    def set_var(self, key: str, value) -> None:
        self.vars[key] = value

    def get_var(self, key: str, default=None):
        return self.vars.get(key, default)

    def replace_placeholders(self, text: str, _depth=0, max_depth=10) -> str:
        if not text:
            return text
        if _depth >= max_depth:
            raise RecursiveVariableError(
                f"变量替换超过最大递归深度({max_depth})，可能存在循环引用"
            )
        result = text
        for key, value in self.vars.items():
            placeholder = "${" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        if "${" in result:
            result = self.replace_placeholders(result, _depth=_depth + 1, max_depth=max_depth)
        return result

    def add_log(self, message: str) -> None:
        self.logs.append(message)
        logger = logging.getLogger("execution")
        logger.info("[%s] %s", self.execution_id, message)
