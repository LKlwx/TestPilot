import os
import uuid
from datetime import datetime
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
                setattr(task, key, val)
            db.session.commit()


@celery_app.task(bind=True, name="ai_generate_api")
def async_ai_generate_api(self, scene: str, user_id: int):
    task_id = self.request.id
    _update_task(task_id, status="running")
    try:
        from service.ai_service import ai_service
        with get_flask_app().app_context():
            result = ai_service.generate_api(scene, user_id)
        _update_task(task_id, status="success", result=str(result), finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())


@celery_app.task(bind=True, name="ai_generate_ui")
def async_ai_generate_ui(self, scene: str, user_id: int):
    task_id = self.request.id
    _update_task(task_id, status="running")
    try:
        from service.ai_service import ai_service
        with get_flask_app().app_context():
            result = ai_service.generate_ui(scene, user_id)
        _update_task(task_id, status="success", result=str(result), finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())


@celery_app.task(bind=True, name="ai_analyze")
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


@celery_app.task(bind=True, name="batch_run")
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
                    cost_time=res.get("cost_time"),
                    response_code=res.get("response_code"),
                    error_msg=res.get("error_msg"),
                )
                db.session.add(result)

            batch.passed = passed
            batch.failed = len(case_ids) - passed
            db.session.commit()
            _update_task(task_id, status="success", result=str({"batch_id": batch.id, "total": len(case_ids), "passed": passed}), finish_time=datetime.now())
    except Exception as e:
        _update_task(task_id, status="failed", error_msg=str(e), finish_time=datetime.now())
