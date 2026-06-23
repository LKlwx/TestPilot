"""数据驱动测试引擎

将 TestDataSet 中的多组数据逐行注入用例，批量执行：

    from service.data_drive import data_drive_execute

    results = data_drive_execute(case, dataset)
    # → [{"status": "PASS", "row_index": 0, ...}, ...]
"""
import json
import csv
import io
from models import TestReport
from extensions import db
from sqlalchemy.exc import SQLAlchemyError
from core.logger import get_logger
from service.test_service import execute_test_case

logger = get_logger(__name__)


def _strip_bom(content):
    """移除 UTF-8 BOM 标记"""
    if content.startswith("\ufeff"):
        return content[1:]
    return content


def data_drive_execute(case, dataset):
    """逐行执行数据驱动测试

    对 dataset.data_rows 中每组数据，用 {{var}} 注入到 case 的 URL/headers/body，
    每行调用 execute_test_case 产生一条独立报告。
    """
    try:
        rows = json.loads(dataset.data_rows) if dataset.data_rows else []
    except (json.JSONDecodeError, TypeError):
        raise ValueError(f"数据集 '{dataset.name}' 的 data_rows 格式错误，应为 JSON 数组")

    if not rows:
        logger.warning("数据集 %s 为空，跳过执行", dataset.name)
        return []

    results = []
    for idx, row in enumerate(rows):
        logger.info("数据驱动执行: case=%s, dataset=%s, row=%d/%d",
                     case.name, dataset.name, idx + 1, len(rows))

        try:
            injected = _inject_row(case, row)
            result = execute_test_case(injected)
            result["row_index"] = idx
            result["row_data"] = row
            logger.info("数据驱动行 %d/%d 完成: status=%s",
                         idx + 1, len(rows), result.get("status"))
        except Exception as e:
            logger.error("数据驱动行 %d/%d 执行异常: %s", idx + 1, len(rows), str(e))
            result = {"status": "ERROR", "row_index": idx, "row_data": row, "error": str(e)}
        results.append(result)

    return results


def _inject_row(case, row):
    """将一行数据注入到用例模板，返回新的 TestCase-like 对象"""
    original_body = _try_parse_json(case.body)
    original_headers = _try_parse_json(case.headers)

    body_replaced = _replace_in_dict(original_body, row)
    headers_replaced = _replace_in_dict(original_headers, row)

    class InjectedCase:
        def __init__(self, original):
            self.id = original.id
            self.name = f"{original.name} [数据行]"
            self.method = original.method
            self.url = _replace_placeholders(original.url, row)
            self.headers = json.dumps(headers_replaced)
            self.body = json.dumps(body_replaced) if isinstance(original_body, dict) else body_replaced
            self.expect = original.expect
            self.extract_var = original.extract_var
            self.timeout = original.timeout
            self.retry = original.retry
            self.tags = original.tags
            self.creator_id = getattr(original, "creator_id", 0)

    return InjectedCase(case)


def _try_parse_json(text):
    """尝试解析 JSON 字符串，解析失败返回原始字符串"""
    if not text:
        return {}
    try:
        return json.loads(text) if isinstance(text, str) else text
    except (json.JSONDecodeError, TypeError):
        return text


def _replace_placeholders(text, row):
    """替换 {{var}} 占位符为数据行中的值（跳过 None 值）"""
    if not isinstance(text, str):
        return text
    for key, val in row.items():
        placeholder = "{{" + key + "}}"
        if placeholder in text and val is not None:
            text = text.replace(placeholder, str(val))
    return text


def _replace_in_dict(obj, row):
    """递归替换 dict/str 中的 {{var}} 占位符"""
    if isinstance(obj, dict):
        return {k: _replace_in_dict(v, row) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_in_dict(v, row) for v in obj]
    if isinstance(obj, str):
        return _replace_placeholders(obj, row)
    return obj


def parse_upload(file_content, filename):
    """解析上传的数据文件，返回数据行列表

    支持格式：
    - .json: JSON 数组 [{"k": "v"}, ...]
    - .csv:  首行为列名的 CSV，后续每行为一行
    """
    name_lower = filename.lower()

    if name_lower.endswith(".json"):
        return json.loads(file_content)

    if name_lower.endswith(".csv"):
        content = _strip_bom(file_content)
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)

    return None
