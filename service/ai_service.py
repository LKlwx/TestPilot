from models import db, AIAgentTask, TestCase, UICase
from agent.ai_agent_core import ai_agent


class AIService:
    """AI 业务层：封装 AI 能力调用与持久化逻辑"""
    @staticmethod
    def generate_api(scene, user_id):
        """生成接口用例并记录任务"""
        res = ai_agent.generate_api_case(scene)
        task = AIAgentTask(task_type="generate_api", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        db.session.commit()
        return res

    @staticmethod
    def generate_ui(scene, user_id):
        """生成 UI 用例并记录任务"""
        res = ai_agent.generate_ui_case(scene)
        task = AIAgentTask(task_type="generate_ui", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        db.session.commit()
        return res

    @staticmethod
    def analyze_log(log, user_id):
        """分析失败日志并保存记录"""
        res = ai_agent.analyze_failure_log(log)
        task = AIAgentTask(task_type="analyze_failure", input_content=log,
                           output_result=res, creator_id=user_id)
        db.session.add(task)
        db.session.commit()
        return res

    @staticmethod
    def save_api(data, user_id):
        """保存生成的接口用例到数据库（自动序列化字典字段）"""
        import json
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
        db.session.commit()

    @staticmethod
    def save_ui(data, user_id):
        """保存生成的 UI 用例到数据库"""
        ui = UICase(name=data["name"], url=data["url"], steps=data.get("steps", ""),
                    creator_id=user_id)
        db.session.add(ui)
        db.session.commit()

    @staticmethod
    def get_history(task_type, user_id, limit=20):
        """查询当前用户的 AI 任务历史记录"""
        tasks = AIAgentTask.query.filter_by(task_type=task_type, creator_id=user_id) \
            .order_by(AIAgentTask.create_time.desc()).limit(limit).all()
        return [{"input": t.input_content, "output": t.output_result, "time": str(t.create_time)} for t in tasks]


ai_service = AIService()
