from datetime import datetime
from extensions import db


class BaseCaseMixin:
    """用例基础抽象类——提取三个用例模型的公有字段"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    create_time = db.Column(db.DateTime, default=datetime.now, index=True)
    tags = db.Column(db.String(500), default="", index=True, comment="用例标签，逗号分隔，如 smoke,regression,critical")
    env_id = db.Column(db.Integer, db.ForeignKey("environment.id", ondelete="SET NULL"), nullable=True, index=True, comment="所属环境ID")
