"""数据迁移：将 TestTask.case_ids 逗号分隔数据迁移到 task_case_association 关联表

用法：
    cd E:\TestPilot
    python scripts\migrate_task_cases.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import TestTask, task_case_association

app = create_app()

def migrate():
    with app.app_context():
        tasks = TestTask.query.all()
        count = 0
        for task in tasks:
            if not task.case_ids:
                continue
            # 解析逗号分隔的 ID
            case_ids = [int(x) for x in task.case_ids.split(",") if x.strip().isdigit()]
            if not case_ids:
                continue
            # 插入关联表
            for case_id in case_ids:
                db.session.execute(
                    task_case_association.insert().values(task_id=task.id, case_id=case_id)
                )
            count += 1
        
        db.session.commit()
        print(f"迁移完成: {count} 个定时任务已处理")

if __name__ == "__main__":
    migrate()
