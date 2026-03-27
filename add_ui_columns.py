from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE ui_case ADD COLUMN loc_type TEXT DEFAULT 'xpath'"))
            print(" 已添加 loc_type")
        except Exception as e:
            print("loc_type 已存在")

        try:
            conn.execute(text("ALTER TABLE ui_case ADD COLUMN loc_value TEXT"))
            print("已添加 loc_value")
        except Exception as e:
            print("loc_value 已存在")

        try:
            conn.execute(text("ALTER TABLE ui_case ADD COLUMN screenshot_path TEXT"))
            print("已添加 screenshot_path")
        except Exception as e:
            print(" screenshot_path 已存在")

        conn.commit()

print("\n🎉 数据库字段已和 models.py 完全对齐！")
