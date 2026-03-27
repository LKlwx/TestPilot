import time
import requests
from concurrent.futures import ThreadPoolExecutor
from extensions import db
from models import PerformanceReport


# 执行性能压测的核心方法
def run_performance(case):
    cost_list = []  # 存储每次请求耗时(ms)
    success_num = 0  # 成功请求数
    fail_num = 0  # 失败请求数

    # 单个请求的执行逻辑
    def single_request():
        nonlocal success_num, fail_num
        try:
            start_time = time.time()
            # 安全解析 headers，防止eval报错
            headers = {}
            try:
                if case.headers and case.headers.strip() != "":
                    headers = eval(case.headers)
            except:
                headers = {}
            # 发送HTTP请求
            requests.request(
                method=case.method,
                url=case.url,
                headers=headers,
                data=case.body,
                timeout=10
            )
            # 记录耗时（毫秒）
            cost_time = round((time.time() - start_time) * 1000, 2)
            cost_list.append(cost_time)
            success_num += 1
        except Exception:
            fail_num += 1

    # 使用线程池实现并发压测
    with ThreadPoolExecutor(max_workers=case.concurrency) as executor:
        # 提交total个请求任务
        for _ in range(case.total):
            executor.submit(single_request)

    # 计算统计指标
    if cost_list:
        avg_time = round(sum(cost_list) / len(cost_list), 2)
        min_time = min(cost_list)
        max_time = max(cost_list)
        total_cost_time = sum(cost_list) / 1000
        qps = round(case.total / total_cost_time, 2)
    else:
        avg_time = min_time = max_time = qps = 0

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
        max_time=max_time
    )
    db.session.add(report)
    db.session.commit()

    return {
        "success": success_num,
        "fail": fail_num,
        "qps": qps,
        "avg_time": avg_time
    }
