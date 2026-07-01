import asyncio
import json
import time
from urllib.parse import urlparse

import aiohttp
import numpy as np
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from core.logger import get_logger
from extensions import db
from models import PerformanceBaseline, PerformanceDetail, PerformanceReport

TIMEOUT = Config.REQUEST_TIMEOUT
logger = get_logger(__name__)


def is_local_url(url):
    """检测是否为本地URL（可能导致压测数据失真）"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname.lower() if parsed.hostname else ""
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):  # nosec B104
            return True
        return False
    except ValueError:
        return False


# 异步压测引擎：asyncio + aiohttp，单线程管理高并发
async def _async_run(case):
    ramp_steps = getattr(case, "ramp_steps", 1) or 1
    steady_duration = getattr(case, "steady_duration", 0) or 0
    logger.info(
        "压测开始: case=%s, url=%s, concurrency=%d, total=%d, ramp=%d, steady=%ds",
        case.name,
        case.url,
        case.concurrency,
        case.total,
        ramp_steps,
        steady_duration,
    )
    cost_list = []
    success = 0
    fail = 0
    qps_series = []  # 每秒请求计数

    is_local = is_local_url(case.url)
    report = PerformanceReport(
        case_id=case.id,
        case_name=case.name,
        concurrency=case.concurrency,
        total=case.total,
        success=0,
        fail=0,
        qps=0,
        avg_time=0,
        min_time=0,
        max_time=0,
        p90=0,
        p99=0,
        success_rate=0,
        is_local=is_local,
    )
    db.session.add(report)
    db.session.flush()

    detail_buffer = []

    def _flush_details():
        if not detail_buffer:
            return
        dicts = [
            {"report_id": report.id, "url": url, "request_time": rt, "status_code": sc} for rt, sc, url in detail_buffer
        ]
        db.session.bulk_insert_mappings(PerformanceDetail, dicts)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
        detail_buffer.clear()

    headers = {}
    try:
        if case.headers and case.headers.strip():
            headers = json.loads(case.headers)
    except (TypeError, json.JSONDecodeError):
        headers = {}

    step_concurrency = max(1, case.concurrency // ramp_steps)
    step_total = case.total // ramp_steps
    remainder = case.total % ramp_steps

    total_start_time = time.time()

    async with aiohttp.ClientSession() as session:
        for step in range(ramp_steps):
            current_concurrency = min(step_concurrency * (step + 1), case.concurrency)
            sem = asyncio.Semaphore(current_concurrency)
            count = step_total + (1 if step < remainder else 0)

            async def single_request(sn=step, sc=sem):
                nonlocal success, fail, qps_series
                async with sc:
                    req_start = time.time()
                    try:
                        content_type = headers.get("Content-Type", "")
                        if "application/json" in content_type and case.body:
                            try:
                                body_json = json.loads(case.body)
                                resp = await session.request(
                                    method=case.method,
                                    url=case.url,
                                    headers=headers,
                                    json=body_json,
                                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                                )
                            except json.JSONDecodeError:
                                resp = await session.request(
                                    method=case.method,
                                    url=case.url,
                                    headers=headers,
                                    data=case.body,
                                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                                )
                        else:
                            resp = await session.request(
                                method=case.method,
                                url=case.url,
                                headers=headers,
                                data=case.body,
                                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                            )

                        cost_time = round((time.time() - req_start) * 1000, 2)
                        if resp.status >= 400:
                            fail += 1
                        else:
                            cost_list.append(cost_time)
                            success += 1
                        detail_buffer.append((cost_time, resp.status, case.url))

                        # 每秒 QPS 计数
                        elapsed = int(time.time() - total_start_time)
                        while len(qps_series) <= elapsed:
                            qps_series.append(0)
                        qps_series[elapsed] += 1

                        if len(detail_buffer) >= 1000:
                            _flush_details()
                    except Exception:
                        fail += 1
                        detail_buffer.append((0, 0, case.url))

            tasks = [single_request() for _ in range(count)]
            await asyncio.gather(*tasks)

            # 阶梯间短暂停顿，让 QPS 曲线可见
            if step < ramp_steps - 1:
                await asyncio.sleep(0.5)

        # 稳态保持（全并发持续发请求）
        if steady_duration > 0:
            steady_count = max(10, case.concurrency * steady_duration // 2)
            tasks = [single_request() for _ in range(steady_count)]
            await asyncio.gather(*tasks)

    total_end_time = time.time()

    _flush_details()

    completed = success + fail
    if cost_list and completed > 0:
        avg_time = round(sum(cost_list) / len(cost_list), 2)
        min_time = min(cost_list)
        max_time = max(cost_list)
        total_time = total_end_time - total_start_time
        qps = round(completed / total_time, 2) if total_time > 0 else 0
        p90 = round(np.percentile(cost_list, 90), 2)
        p99 = round(np.percentile(cost_list, 99), 2)
        success_rate = round((success / completed) * 100, 2) if completed > 0 else 0
    else:
        avg_time = min_time = max_time = qps = 0
        p90 = p99 = success_rate = 0

    report.success = success
    report.fail = fail
    report.qps = qps
    report.avg_time = avg_time
    report.min_time = min_time
    report.max_time = max_time
    report.p90 = p90
    report.p99 = p99
    report.success_rate = success_rate
    report.extra = json.dumps({"qps_series": qps_series}, ensure_ascii=False)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    logger.info(
        "压测完成: case=%s, success=%d, fail=%d, qps=%s, p90=%s, p99=%s", case.name, success, fail, qps, p90, p99
    )
    logger.info(
        json.dumps(
            {
                "event": "perf_test_completed",
                "case_id": case.id,
                "case_name": case.name,
                "status": "done",
                "success": success,
                "fail": fail,
                "qps": qps,
                "p90": p90,
                "p99": p99,
                "ramp_steps": ramp_steps,
                "steady_duration": steady_duration,
            },
            ensure_ascii=False,
        )
    )

    # 对比基线
    degradation = None
    baseline = db.session.query(PerformanceBaseline).filter_by(case_id=case.id).first()
    if baseline and baseline.p90:
        pct = round((p90 - baseline.p90) / baseline.p90 * 100, 1)
        if pct >= 20:
            level = "severe"
        elif pct >= 10:
            level = "minor"
        elif pct <= -20:
            level = "improved"
        else:
            level = "stable"
        degradation = {
            "level": level,
            "pct": pct,
            "baseline_p90": round(baseline.p90, 2),
            "baseline_p99": round(baseline.p99, 2) if baseline.p99 else None,
            "baseline_avg": round(baseline.avg_time, 2) if baseline.avg_time else None,
            "baseline_qps": round(baseline.qps, 2) if baseline.qps else None,
        }

    return {
        "success": success,
        "fail": fail,
        "qps": qps,
        "avg_time": avg_time,
        "p90": p90,
        "p99": p99,
        "success_rate": success_rate,
        "degradation": degradation,
    }


def run_performance(case):
    """同步入口，内部启动 asyncio 事件循环"""
    return asyncio.run(_async_run(case))
