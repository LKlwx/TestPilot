from models import db, AIAgentTask, TestCase, UICase
from agent.ai_agent_core import ai_agent


class AIService:
    @staticmethod
    def generate_api(scene, user_id):
        res = ai_agent.generate_api_case(scene)
        task = AIAgentTask(task_type="generate_api", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        db.session.commit()
        return res

    @staticmethod
    def generate_ui(scene, user_id):
        res = ai_agent.generate_ui_case(scene)
        task = AIAgentTask(task_type="generate_ui", input_content=scene,
                           output_result=str(res), creator_id=user_id)
        db.session.add(task)
        db.session.commit()
        return res

    @staticmethod
    def analyze_log(log, user_id):
        res = ai_agent.analyze_failure_log(log)
        task = AIAgentTask(task_type="analyze_failure", input_content=log,
                           output_result=res, creator_id=user_id)
        db.session.add(task)
        db.session.commit()
        return res

    @staticmethod
    def save_api(data, user_id):
        case = TestCase(name=data["name"], method=data["method"], url=data["url"],
                        headers=data.get("headers", "{}"), body=data.get("body", "{}"),
                        expect=data.get("expect"), creator_id=user_id)
        db.session.add(case)
        db.session.commit()

    @staticmethod
    def save_ui(data, user_id):
        ui = UICase(name=data["name"], url=data["url"], steps=data.get("steps", ""),
                    creator_id=user_id)
        db.session.add(ui)
        db.session.commit()


ai_service = AIService()
