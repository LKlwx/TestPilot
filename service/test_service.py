import requests
import json
from models import TestReport
from extensions import db
import time


def execute_test_case(case):
    start_time = time.time()
    try:
        try:
            headers = json.loads(case.headers) if case.headers else {}
        except:
            headers = {}

        try:
            body = json.loads(case.body) if case.body else None
        except:
            body = None

        resp = requests.request(
            method=case.method,
            url=case.url,
            headers=headers,
            json=body,
            timeout=10
        )

        # 计算耗时
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
            "case_id": case.id,
            "name": case.name,
            "status": report.status,
            "code": resp.status_code,
            "time": report.cost_time,
            "msg": msg
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

        return {
            "status": "ERROR",
            "time": cost_time,
            "error": str(e)
        }
