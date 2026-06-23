import os
import uuid
import json
from datetime import datetime, timedelta
from celery import Celery
from config import Config
from core.execution_context import ExecutionContext

REDIS_URL = Config.REDIS_URL

celery_app = Celery(
    "testpilot",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# 定时任务调度（启动 Celery Beat 或 worker -B 时生效）
celery_app.conf.beat_schedule = {
    "cleanup-old-perf-details": {
        "task": "cleanup_perf_details",
        "schedule": timedelta(hours=24),
        "args": [],
    },
}


_flask_app = None


def get_flask_app():
    """获取当前 Worker 进程的 Flask 应用实例（懒加载，每个进程初始化一次）"""
    global _flask_app
    if _flask_app is None:
        from app import create_app
        _flask_app = create_app(os.environ.get("FLASK_ENV", "development"))
    return _flask_app


def _update_task(task_id: str, **kwargs):
    """更新 AsyncTask 记录的 helper"""
    from extensions import db
    from models import AsyncTask
    app = get_flask_app()
    with app.app_context():
        task = AsyncTask.query.get(task_id)
        if task:
            for key, val in kwargs.items():
                if key == "result" and isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                setattr(task, key, val)
            db.session.commit()


@celery_app.task(
    bind=True, name="ai_generate_api",
    task_time_limit=300, task_soft_time_limit=240,
    autoretry_for=(Exception,), retry_backoff=True, max_retries=3,
)
def async_ai_generate_api(self, scene: str, user_id: int):
    task_id = self.request.id
    _update_task(task_id, status="running")
    try:
        from service.ai_service import ai_service
        with get_flask_app().app_context():
            result = ai_service.generate_api(scene, user_id)
        _update_task(task_id, status="success", result=result, finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())


@celery_app.task(
    bind=True, name="ai_generate_ui",
    task_time_limit=300, task_soft_time_limit=240,
    autoretry_for=(Exception,), retry_backoff=True, max_retries=3,
)
def async_ai_generate_ui(self, scene: str, user_id: int):
    task_id = self.request.id
    _update_task(task_id, status="running")
    try:
        from service.ai_service import ai_service
        with get_flask_app().app_context():
            result = ai_service.generate_ui(scene, user_id)
        _update_task(task_id, status="success", result=result, finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())


@celery_app.task(
    bind=True, name="ai_analyze",
    task_time_limit=300, task_soft_time_limit=240,
    autoretry_for=(Exception,), retry_backoff=True, max_retries=3,
)
def async_ai_analyze(self, log: str, user_id: int):
    task_id = self.request.id
    _update_task(task_id, status="running")
    try:
        from service.ai_service import ai_service
        with get_flask_app().app_context():
            result = ai_service.analyze_log(log, user_id)
        _update_task(task_id, status="success", result=str(result), finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())


@celery_app.task(
    bind=True, name="batch_run",
    task_time_limit=600, task_soft_time_limit=500,
    autoretry_for=(Exception,), retry_backoff=True, max_retries=2,
)
def async_batch_run(self, case_ids: list, user_id: int):
    task_id = self.request.id
    _update_task(task_id, status="running")
    try:
        from service.test_service import execute_test_case
        from models import TestCase, BatchTask, BatchResult
        from extensions import db
        app = get_flask_app()
        with app.app_context():
            batch = BatchTask(total=len(case_ids), creator_id=user_id)
            db.session.add(batch)
            db.session.flush()

            passed = 0
            ctx = ExecutionContext()
            for cid in case_ids:
                case = TestCase.query.get(cid)
                if not case:
                    continue
                res = execute_test_case(case, ctx)
                status = "pass" if res.get("status", "").upper() == "PASS" else "fail"
                if status == "pass":
                    passed += 1
                result = BatchResult(
                    batch_id=batch.id,
                    case_id=cid,
                    case_name=case.name,
                    status=status,
                    cost_time=res.get("time"),
                    response_code=res.get("code"),
                    error_msg=res.get("error") or res.get("msg", ""),
                )
                db.session.add(result)

            batch.passed = passed
            batch.failed = len(case_ids) - passed
            db.session.commit()
            _update_task(task_id, status="success", result={"batch_id": batch.id, "total": len(case_ids), "passed": passed}, finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())


@celery_app.task(name="cleanup_perf_details")
def cleanup_perf_details():
    """定时清理过期压测明细数据（保留 N 天，汇总报告保留）"""
    from extensions import db
    from models import PerformanceDetail
    from config import Config
    retention_days = Config.PERF_DETAIL_RETENTION_DAYS
    cutoff = datetime.now() - timedelta(days=retention_days)

    app = get_flask_app()
    with app.app_context():
        from models import PerformanceReport
        old_report_ids = db.session.query(PerformanceReport.id).filter(
            PerformanceReport.create_time < cutoff
        ).subquery()

        deleted = db.session.query(PerformanceDetail).filter(
            PerformanceDetail.report_id.in_(old_report_ids)
        ).delete(synchronize_session=False)
        db.session.commit()
        if deleted:
            from core.logger import get_logger
            get_logger(__name__).info("已清理 %d 条过期压测明细数据（保留 %d 天）", deleted, retention_days)
