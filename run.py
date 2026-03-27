from app import create_app
from extensions import db
from models import User

app = create_app("development")

# 初始化数据库
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
