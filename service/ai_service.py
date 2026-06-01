import json
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import AIAgentTask, TestCase, UICase
from agent.ai_agent_core import ai_agent
from core.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """AI 业务层：封装 AI 能力调用与持久化逻辑"""
    @staticmethod
    def generate_api(scene, user_id):
        logger.info("AI 生成接口用例: scene=%s, user_id=%d", scene[:50], user_id)
        try:
            res = ai_agent.generate_api_case(scene)
        except Exception as e:
            logger.error("AI 生成接口用例失败: %s", str(e), exc_info=True)
            raise
        task = AIAgentTask(task_type="generate_api", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
        return res

    @staticmethod
    def generate_ui(scene, user_id):
        logger.info("AI 生成 UI 用例: scene=%s, user_id=%d", scene[:50], user_id)
        try:
            res = ai_agent.generate_ui_case(scene)
        except Exception as e:
            logger.error("AI 生成 UI 用例失败: %s", str(e), exc_info=True)
            raise
        task = AIAgentTask(task_type="generate_ui", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
        return res

    @staticmethod
    def analyze_log(log, user_id):
        logger.info("AI 分析日志: user_id=%d, log_len=%d", user_id, len(log))
        try:
            res = ai_agent.analyze_failure_log(log)
        except Exception as e:
            logger.error("AI 分析日志失败: %s", str(e), exc_info=True)
            raise
        task = AIAgentTask(task_type="analyze_failure", input_content=log,
                           output_result=res, creator_id=user_id)
        db.session.add(task)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
        return res

    @staticmethod
    def generate_ui(scene, user_id):
        res = ai_agent.generate_ui_case(scene)
        task = AIAgentTask(task_type="generate_ui", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
        return res

    @staticmethod
    def analyze_log(log, user_id):
        """分析失败日志并保存记录"""
        res = ai_agent.analyze_failure_log(log)
        task = AIAgentTask(task_type="analyze_failure", input_content=log,
                           output_result=res, creator_id=user_id)
        db.session.add(task)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
        return res

    @staticmethod
    def save_api(data, user_id):
        logger.info("AI 保存接口用例: name=%s, user_id=%d", data.get("name", ""), user_id)
        headers = data.get("headers", {})
        body = data.get("body", {})
        if isinstance(headers, dict):
            headers = json.dumps(headers, ensure_ascii=False)
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False)
        case = TestCase(name=data["name"], method=data["method"], url=data["url"],
                        headers=headers, body=body,
                        expect=data.get("expect"), creator_id=user_id)
        db.session.add(case)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise

    @staticmethod
    def save_ui(data, user_id):
        logger.info("AI 保存 UI 用例: name=%s, user_id=%d", data.get("name", ""), user_id)
        ui = UICase(name=data["name"], url=data["url"], steps=data.get("steps", ""),
                    creator_id=user_id)
        db.session.add(ui)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise

    @staticmethod
    def get_history(task_type, user_id, limit=20):
        """查询当前用户的 AI 任务历史记录"""
        tasks = AIAgentTask.query.filter_by(task_type=task_type, creator_id=user_id) \
            .order_by(AIAgentTask.create_time.desc()).limit(limit).all()
        return [{"input": t.input_content, "output": t.output_result, "time": str(t.create_time)} for t in tasks]


ai_service = AIService()
