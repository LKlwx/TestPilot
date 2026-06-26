import json
import re
from contextlib import contextmanager
from models import TestReport
from extensions import db
import time
from sqlalchemy.exc import SQLAlchemyError
from core.logger import get_logger
from core.execution_context import ExecutionContext
from core.assert_engine import AssertEngine
from core.http_client import BaseHTTPClient
from config import Config

TIMEOUT = Config.REQUEST_TIMEOUT

logger = get_logger(__name__)


@contextmanager
def _allure_step(name: str):
    """条件式 allure.step，无 allure 环境时静默跳过"""
    try:
        import allure
        with allure.step(name):
            yield
    except ImportError:
        yield


# HTTP 客户端（BaseHTTPClient 封装了 Session + 拦截器 + 链式断言 + 全链路日志）
_http_client = BaseHTTPClient(timeout=TIMEOUT)


def _merge_retry_results(attempts, max_retries):
    """合并多次执行结果，确定最终状态

    - 全部成功 → PASS
    - 前 N 次失败、最终通过 → FLAKY（标记重试次数）
    - 全部失败 → 最后一次的状态（FAIL 或 ERROR）
    """
    final = attempts[-1]
    retried = len(attempts) - 1
    any_success = any(a.get("status") == "PASS" for a in attempts)

    if any_success and retried > 0:
        status = "FLAKY"
    else:
        status = final.get("status", "ERROR")

    return {
        "status": status,
        "retried": retried,
        "code": final.get("code", 0),
        "time": final.get("time", 0),
        "body": final.get("body", ""),
        "msg": final.get("msg", ""),
        "error": final.get("error", ""),
        "current_vars": final.get("current_vars", {}),
    }


def check_flaky(case):
    """检查用例近 5 次执行中 FLAKY 占比，自动标记为稳定/不稳定"""
    recent = TestReport.query.filter_by(case_id=case.id)\
        .order_by(TestReport.create_time.desc())\
        .limit(5).all()
    flaky_count = sum(1 for r in recent if r.status == "FLAKY")
    case.unstable = flaky_count >= 3
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def execute_test_case(case, context=None):
    """执行接口测试用例，支持配置化重试 + FLAKY 判定

    重试逻辑：
    - case.retry = 0（默认）：不重试，一次出结果
    - case.retry = N ：失败后最多重试 N 次
    - 重试后通过 → FLAKY（黄色警告）
    - 重试仍失败 → 最后一次结果（FAIL 或 ERROR）
    - 所有执行只产生一条 TestReport
    """
    if context is None:
        context = ExecutionContext()
    timeout = getattr(case, "timeout", TIMEOUT) or TIMEOUT
    max_retries = max(0, getattr(case, "retry", 0) or 0)

    attempts = []
    for attempt in range(max_retries + 1):
        result = _execute_raw(case, context, timeout)
        attempts.append(result)
        if result.get("status") == "PASS":
            break
        if attempt < max_retries:
            logger.info(f"用例 {case.id} 第 {attempt + 1} 次失败，准备重试")
            time.sleep(2)

    merged = _merge_retry_results(attempts, max_retries)
    _create_report(case, merged)
    check_flaky(case)
    return merged


def _create_report(case, merged):
    """根据合并结果创建单条测试报告"""
    report = TestReport(
        case_id=case.id,
        case_name=case.name,
        status=merged["status"],
        retried=merged["retried"],
        cost_time=merged["time"],
        response_code=merged["code"],
        response_body=merged.get("body", ""),
        error_msg=merged.get("error") or merged.get("msg", ""),
    )
    db.session.add(report)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    logger.info(json.dumps({
        "event": "test_executed", "case_id": case.id,
        "status": report.status, "retried": report.retried,
        "duration_ms": round(merged["time"] * 1000),
        "response_code": merged["code"],
    }, ensure_ascii=False))


def _execute_raw(case, context, timeout):
    """单次执行引擎：纯执行 + 断言，不创建报告"""
    start_time = time.time()
    try:
        with _allure_step("变量替换"):
            final_url = context.replace_placeholders(case.url)
            final_body = context.replace_placeholders(case.body)

        # 解析环境变量与 base_url
        env = None
        try:
            from models import Environment
            env_id = getattr(case, "env_id", None)
            if env_id:
                env = Environment.query.get(env_id)
            if not env:
                env = Environment.query.filter_by(is_default=True).first()
        except Exception:
            pass

        if env:
            # 环境 base_url + 用例相对路径
            if not final_url.startswith("http"):
                final_url = f"{env.base_url.rstrip('/')}{final_url}"
            try:
                import json
                env_vars = json.loads(env.variables) if env.variables else {}
                for k, v in env_vars.items():
                    if not context.get_var(k):
                        context.set_var(k, v)
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                env_headers = json.loads(env.headers) if env.headers else {}
            except (json.JSONDecodeError, TypeError):
                env_headers = {}
        else:
            env_headers = {}

        # 环境 headers 为基，用例 headers 覆盖
        try:
            case_headers = json.loads(case.headers) if case.headers else {}
        except (TypeError, json.JSONDecodeError):
            case_headers = {}
        merged = {**env_headers, **case_headers}
        headers = merged

        try:
            body = json.loads(final_body) if final_body else None
        except (TypeError, json.JSONDecodeError):
            raise ValueError(f"请求体 JSON 格式错误，请检查用例 Body 配置: {final_body[:200]}")

        with _allure_step("发送 HTTP 请求"):
            hr = _http_client.request(
                method=case.method,
                url=final_url,
                headers=headers,
                json=body,
                timeout=timeout,
            )
        resp = hr.resp
        resp.encoding = 'utf-8'

        # 标记接口覆盖（可选功能，失败不影响测试主流程）
        try:
            from api.coverage import _mark_covered
        except ImportError:
            pass
        else:
            try:
                _mark_covered(case.method, final_url, getattr(case, "creator_id", 0))
            except Exception:
                pass

        # 从响应中提取变量存入变量池
        if case.extract_var and "=" in case.extract_var:
            try:
                var_name, path = case.extract_var.split("=", 1)
                var_name = var_name.strip()
                resp_json = resp.json()

                keys = path.strip().replace("$.", "").split(".")
                val = resp_json
                for k in keys:
                    val = val[k]

                context.set_var(var_name, val)
                logger.info(f"变量提取成功: {var_name} = {val}")
            except (KeyError, TypeError, IndexError) as e:
                logger.error(f"变量提取失败: {str(e)}", exc_info=True)

        cost_time = round(time.time() - start_time, 3)

        # 断言检查
        passed = True
        msg = ""
        with _allure_step("断言校验"):
            engine = AssertEngine(response=resp, cost_time=cost_time)
            if case.expect:
                passed, msg = engine.execute(case.expect)

        # 自动 Schema 校验（匹配 ApiContract）
        try:
            from urllib.parse import urlparse
            from models import ApiContract
            path = urlparse(final_url).path
            endpoint_exact = f"{case.method} {path.rstrip('/')}"
            contract = ApiContract.query.filter_by(endpoint=endpoint_exact).first()

            if not contract:
                contracts = ApiContract.query.all()
                for c in contracts:
                    c_method, c_path = c.endpoint.split(" ", 1) if " " in c.endpoint else ("", "")
                    if c_method == case.method:
                        pattern = re.sub(r"\{[^}]+\}", r"[^/]+", c_path)
                        if re.match("^" + pattern + "$", path.rstrip("/")):
                            contract = c
                            break

            if contract and contract.response_schema and passed:
                try:
                    resp_json = resp.json()
                    schema_passed, schema_msg = engine.validate_schema(resp_json, contract.response_schema)
                    if not schema_passed:
                        passed = False
                        msg += f" | {schema_msg}"
                except (json.JSONDecodeError, ValueError):
                    pass
        except Exception:
            pass

        # Allure 上下文检测与附加
        try:
            import allure
            allure.attach(resp.text[:5000], name="response_body",
                          attachment_type=allure.attachment_type.TEXT)
            if not passed:
                allure.attach(f"断言失败: {msg}", name="assertion_error",
                              attachment_type=allure.attachment_type.TEXT)
        except ImportError:
            pass

        logger.info(json.dumps({
            "event": "test_raw_executed", "case_id": case.id,
            "status": "PASS" if passed else "FAIL",
            "duration_ms": round(cost_time * 1000),
            "response_code": resp.status_code,
        }, ensure_ascii=False))

        return {
            "status": "PASS" if passed else "FAIL",
            "code": resp.status_code,
            "time": cost_time,
            "body": resp.text[:1000],
            "msg": msg,
            "current_vars": dict(context.vars),
        }

    except Exception as e:
        cost_time = round(time.time() - start_time, 3)

        try:
            import allure
            allure.attach(str(e)[:5000], name="error_info",
                          attachment_type=allure.attachment_type.TEXT)
        except ImportError:
            pass

        logger.info(json.dumps({
            "event": "test_raw_executed", "case_id": case.id,
            "status": "ERROR", "duration_ms": round(cost_time * 1000),
            "error": str(e)[:200],
        }, ensure_ascii=False))

        return {"status": "ERROR", "time": cost_time, "error": str(e), "current_vars": dict(context.vars)}
