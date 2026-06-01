import requests
import json
from models import TestReport
from extensions import db
import time
from sqlalchemy.exc import SQLAlchemyError
from core.logger import get_logger
from core.execution_context import ExecutionContext
from core.assert_engine import AssertEngine
from config import Config

TIMEOUT = Config.REQUEST_TIMEOUT

logger = get_logger(__name__)

# 复用 HTTP Session（Keep-Alive 连接池，减少 TCP 握手）
_http_session = requests.Session()


def execute_test_case(case, context=None):
    if context is None:
        context = ExecutionContext()
    timeout = getattr(case, "timeout", TIMEOUT) or TIMEOUT
    max_retries = getattr(case, "retry", 0) or 0
    last_result = None

    for attempt in range(max_retries + 1):
        result = _do_execute(case, context, timeout)
        if attempt < max_retries and result.get("status") in ("ERROR", "FAIL"):
            logger.info("用例 %d 第 %d 次执行失败，准备重试", case.id, attempt + 1)
            last_result = result
            time.sleep(1)
        else:
            return result
    return last_result


def _do_execute(case, context, timeout):
    start_time = time.time()
    try:
        final_url = context.replace_placeholders(case.url)
        final_body = context.replace_placeholders(case.body)

        try:
            headers = json.loads(case.headers) if case.headers else {}
        except (TypeError, json.JSONDecodeError):
            headers = {}

        try:
            body = json.loads(final_body) if final_body else None
        except (TypeError, json.JSONDecodeError):
            raise ValueError(f"请求体 JSON 格式错误，请检查用例 Body 配置: {final_body[:200]}")

        resp = _http_session.request(
            method=case.method,
            url=final_url,
            headers=headers,
            json=body,
            timeout=timeout
        )
        resp.encoding = 'utf-8'

        # 标记接口覆盖
        try:
            from api.coverage import _mark_covered
            _mark_covered(case.method, final_url, getattr(case, "creator_id", 0))
        except Exception:
            pass

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

        # 断言检查（使用 AssertEngine 支持多种断言类型）
        passed = True
        msg = ""
        engine = AssertEngine(response=resp, cost_time=cost_time)
        if case.expect:
            passed, msg = engine.execute(case.expect)

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
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise

        logger.info(json.dumps({
            "event": "test_executed", "case_id": case.id,
            "status": report.status, "duration_ms": round(cost_time * 1000),
            "response_code": resp.status_code,
        }, ensure_ascii=False))

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
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
        logger.info(json.dumps({
            "event": "test_executed", "case_id": case.id,
            "status": "ERROR", "duration_ms": round(cost_time * 1000),
            "error": str(e)[:200],
        }, ensure_ascii=False))
        return {"status": "ERROR", "time": cost_time, "error": str(e)}
