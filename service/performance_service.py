import time
import requests
import json
import numpy as np
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from extensions import db
from models import PerformanceReport, PerformanceDetail


def is_local_url(url):
    """检测是否为本地URL（可能导致压测数据失真）"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname.lower() if parsed.hostname else ""
        port = parsed.port
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return True
        if host == "localhost":
            return True
        return False
    except:
        return False


# 执行性能压测的核心方法
def run_performance(case):
    cost_list = []  # 存储每次请求耗时(ms)
    detail_list = []  # 存储明细数据 (耗时，状态码)
    success_num = 0  # 成功请求数
    fail_num = 0  # 失败请求数
    lock = Lock()  # 线程锁

    # 单个请求的执行逻辑
    def single_request():
        nonlocal success_num, fail_num
        try:
            start_time = time.time()
            headers = {}
            try:
                if case.headers and case.headers.strip() != "":
                    headers = json.loads(case.headers)
            except:
                headers = {}
            
            resp = requests.request(
                method=case.method,
                url=case.url,
                headers=headers,
                data=case.body,
                timeout=10
            )
            # 记录耗时（毫秒）
            cost_time = round((time.time() - start_time) * 1000, 2)
            
            # HTTP 状态码 >= 400 算失败
            if resp.status_code >= 400:
                with lock:
                    fail_num += 1
                    detail_list.append((cost_time, resp.status_code, case.url))
            else:
                with lock:
                    cost_list.append(cost_time)
                    detail_list.append((cost_time, resp.status_code, case.url))
                    success_num += 1
        except Exception:
            with lock:
                fail_num += 1
                detail_list.append((0, 0, case.url))

    # 使用线程池实现并发压测
    total_start_time = time.time()
    with ThreadPoolExecutor(max_workers=case.concurrency) as executor:
        for _ in range(case.total):
            executor.submit(single_request)
    total_end_time = time.time()

    # 计算统计指标
    completed = success_num + fail_num
    if cost_list and completed > 0:
        avg_time = round(sum(cost_list) / len(cost_list), 2)
        min_time = min(cost_list)
        max_time = max(cost_list)
        total_time = total_end_time - total_start_time
        # 用实际完成的请求数计算 QPS
        qps = round(completed / total_time, 2) if total_time > 0 else 0

        p90 = round(np.percentile(cost_list, 90), 2)
        p99 = round(np.percentile(cost_list, 99), 2)
        # 加除零保护
        success_rate = round((success_num / completed) * 100, 2) if completed > 0 else 0
    else:
        avg_time = min_time = max_time = qps = 0
        p90 = p99 = success_rate = 0

    # 保存测试报告到数据库
    is_local = is_local_url(case.url)
    report = PerformanceReport(
        case_id=case.id,
        case_name=case.name,
        concurrency=case.concurrency,
        total=case.total,
        success=success_num,
        fail=fail_num,
        qps=qps,
        avg_time=avg_time,
        min_time=min_time,
        max_time=max_time,
        p90=p90,
        p99=p99,
        success_rate=success_rate,
        is_local=is_local,
    )
    db.session.add(report)
    db.session.commit()  # 先提交报告，获取 report.id

    # 批量保存明细数据
    for rt, sc, url in detail_list:
        detail = PerformanceDetail(
            report_id=report.id,
            url=url,
            request_time=rt,
            status_code=sc
        )
        db.session.add(detail)
    db.session.commit()

    return {
        "success": success_num,
        "fail": fail_num,
        "qps": qps,
        "avg_time": avg_time,
        "p90": p90,
        "p99": p99,
        "success_rate": success_rate
    }
