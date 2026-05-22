from datetime import datetime
from extensions import db


class BaseCaseMixin:
    """用例基础抽象类——提取三个用例模型的公有字段

    仅抽取三者都有的字段：id, name, create_time
    creator_id 和 update_time 各有缺失，留在各自模型中按需声明
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    create_time = db.Column(db.DateTime, default=datetime.now, index=True)
