import time
import requests
import json
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from extensions import db
from models import PerformanceReport, PerformanceDetail


# 执行性能压测的核心方法
def run_performance(case):
    cost_list = []  # 存储每次请求耗时(ms)
    detail_list = []  # 存储明细数据 (耗时，状态码)
    success_num = 0  # 成功请求数
    fail_num = 0  # 失败请求数

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
            cost_list.append(cost_time)
            detail_list.append((cost_time, resp.status_code))
            success_num += 1
        except Exception:
            fail_num += 1
            # 失败请求也记录，耗时记为 0 或超时时间
            detail_list.append((0, 0))

    # 使用线程池实现并发压测
    with ThreadPoolExecutor(max_workers=case.concurrency) as executor:
        for _ in range(case.total):
            executor.submit(single_request)

    # 计算统计指标
    if cost_list:
        avg_time = round(sum(cost_list) / len(cost_list), 2)
        min_time = min(cost_list)
        max_time = max(cost_list)
        total_cost_time = sum(cost_list) / 1000
        qps = round(case.total / total_cost_time, 2)

        p90 = round(np.percentile(cost_list, 90), 2)
        p99 = round(np.percentile(cost_list, 99), 2)
        success_rate = round((success_num / case.total) * 100, 2)
    else:
        avg_time = min_time = max_time = qps = 0
        p90 = p99 = success_rate = 0

    # 保存测试报告到数据库
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
    )
    db.session.add(report)
    db.session.commit()  # 先提交报告，获取 report.id

    # 批量保存明细数据
    for rt, sc in detail_list:
        detail = PerformanceDetail(
            report_id=report.id,
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
