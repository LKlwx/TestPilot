import requests
import json
from models import TestReport
from extensions import db
import time
from core.logger import get_logger
from core.execution_context import ExecutionContext

logger = get_logger(__name__)


def execute_test_case(case, context=None):
    if context is None:
        context = ExecutionContext()
    start_time = time.time()
    try:
        final_url = context.replace_placeholders(case.url)
        final_body = context.replace_placeholders(case.body)

        try:
            headers = json.loads(case.headers) if case.headers else {}
        except:
            headers = {}

        try:
            body = json.loads(final_body) if final_body else None
        except:
            body = None

        resp = requests.request(
            method=case.method,
            url=final_url,
            headers=headers,
            json=body,
            timeout=10
        )
        resp.encoding = 'utf-8'

        # 从响应中提取变量存入变量池
        if case.extract_var and "=" in case.extract_var:
            try:
                var_name, path = case.extract_var.split("=", 1)
                var_name = var_name.strip()
                resp_json = resp.json()

                # 简单的 JSON 路径解析 (支持 $.key.subkey)
                keys = path.strip().replace("$.", "").split(".")
                val = resp_json
                for k in keys:
                    val = val[k]

                context.set_var(var_name, val)
                logger.info(f"变量提取成功: {var_name} = {val}")
            except Exception as e:
                logger.error(f"变量提取失败: {str(e)}", exc_info=True)

        cost_time = round(time.time() - start_time, 3)
        passed = True
        msg = ""
        if case.expect and case.expect not in resp.text:
            passed = False
            msg = f"预期内容不存在：{case.expect}"

        report = TestReport(
            case_id=case.id,
            case_name=case.name,
            status="PASS" if passed else "FAIL",
            cost_time=cost_time,
            response_code=resp.status_code,
            response_body=resp.text[:1000],
            error_msg=msg
        )
        db.session.add(report)
        db.session.commit()

        return {
            "status": report.status,
            "code": resp.status_code,
            "time": cost_time,
            "msg": msg,
            "current_vars": dict(context.vars)
        }

    except Exception as e:
        cost_time = round(time.time() - start_time, 3)
        report = TestReport(
            case_id=case.id,
            case_name=case.name,
            status="ERROR",
            cost_time=cost_time,
            response_code=0,
            response_body="",
            error_msg=str(e)
        )
        db.session.add(report)
        db.session.commit()
        return {"status": "ERROR", "time": cost_time, "error": str(e)}
