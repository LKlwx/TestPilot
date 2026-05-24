import uuid
import time
import logging


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

    def replace_placeholders(self, text: str) -> str:
        if not text:
            return text
        for key, value in self.vars.items():
            placeholder = "${" + key + "}"
            if placeholder in text:
                text = text.replace(placeholder, str(value))
        return text

    def add_log(self, message: str) -> None:
        self.logs.append(message)
        logger = logging.getLogger("execution")
        logger.info("[%s] %s", self.execution_id, message)
