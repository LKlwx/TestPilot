from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


# ------------------------------
# 用户表（登录、权限）
# ------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(100), unique=True)
    role = db.Column(db.String(20), default="tester")  # admin/tester
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ------------------------------
# 测试用例表
# ------------------------------
class TestCase(db.Model):
    __tablename__ = "test_case"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50),default="默认模块",comment="所属模块")
    method = db.Column(db.String(10), nullable=False)  # GET/POST/PUT/DELETE
    url = db.Column(db.String(500), nullable=False)
    headers = db.Column(db.Text, default="{}")
    body = db.Column(db.Text, default="{}")
    expect = db.Column(db.String(200))  # 预期结果关键字
    extract_var = db.Column(db.String(200), comment="后置提取：格式如 token=$.args.token")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    # module = db.Column(db.String(50), default="default")


# ------------------------------
# 测试报告表
# ------------------------------
class TestReport(db.Model):
    __tablename__ = "test_report"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("test_case.id"))
    case_name = db.Column(db.String(100))
    status = db.Column(db.String(20))  # pass/fail/error
    cost_time = db.Column(db.Float)  # 耗时（秒）
    response_code = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    error_msg = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.now)


# ------------------------------
# 定时任务表
# ------------------------------
class TestTask(db.Model):
    __tablename__ = "test_task"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    cron_expr = db.Column(db.String(50))  # 定时表达式，如 "0 0 * * *"
    case_ids = db.Column(db.Text)  # 要执行的用例ID列表，逗号分隔
    status = db.Column(db.String(20), default="enabled")  # enabled/disabled
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    create_time = db.Column(db.DateTime, default=datetime.now)


# ------------------------------
# UI 自动化用例表
# ------------------------------
class UICase(db.Model):
    __tablename__ = "ui_case"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    steps = db.Column(db.Text)  # 操作步骤
    loc_type = db.Column(db.String(20), default="xpath", comment="元素定位方式：id/xpath/css")
    loc_value = db.Column(db.String(500), comment="元素定位值")
    screenshot_path = db.Column(db.String(500), comment="测试截图路径")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


# ------------------------------
# UI 自动化测试报告表
# ------------------------------
class UIReport(db.Model):
    __tablename__ = "ui_report"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("ui_case.id"))
    case_name = db.Column(db.String(100))
    status = db.Column(db.String(20))  # pass/fail/error
    cost_time = db.Column(db.Float)
    error_msg = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.now)


# 性能测试用例表：存储压测的地址、并发、请求总数等配置
class PerformanceCase(db.Model):
    __tablename__ = "performance_case"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 用例名称
    url = db.Column(db.String(500), nullable=False)  # 压测URL
    method = db.Column(db.String(10), default="GET")  # 请求方法
    headers = db.Column(db.Text, default="{}")  # 请求头
    body = db.Column(db.Text)  # 请求体
    concurrency = db.Column(db.Integer, default=10)  # 并发线程数
    total = db.Column(db.Integer, default=50)  # 总请求次数
    create_time = db.Column(db.DateTime, default=datetime.now)


# 性能测试报告表：存储每次压测的结果数据
class PerformanceReport(db.Model):
    __tablename__ = "performance_report"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer)  # 对应的用例ID
    case_name = db.Column(db.String(100))  # 用例名称
    concurrency = db.Column(db.Integer)  # 并发数
    total = db.Column(db.Integer)  # 总请求数
    success = db.Column(db.Integer)  # 成功次数
    fail = db.Column(db.Integer)  # 失败次数
    qps = db.Column(db.Float)  # 每秒请求数
    avg_time = db.Column(db.Float)  # 平均响应时间(ms)
    min_time = db.Column(db.Float)  # 最小响应时间(ms)
    max_time = db.Column(db.Float)  # 最大响应时间(ms)
    create_time = db.Column(db.DateTime, default=datetime.now)
    p90 = db.Column(db.Float, default=0)
    p99 = db.Column(db.Float, default=0)
    success_rate = db.Column(db.Float, default=0)


# AI 智能测试任务记录表
class AIAgentTask(db.Model):
    __tablename__ = "ai_agent_task"

    id = db.Column(db.Integer, primary_key=True, comment="主键ID")
    # 任务类型：generate_api=生成接口用例 generate_ui=生成UI用例 analyze_failure=失败分析 summarize_report=报告总结
    task_type = db.Column(db.String(32), nullable=False, comment="任务类型")
    input_content = db.Column(db.Text, nullable=False, comment="用户输入内容")
    output_result = db.Column(db.Text, nullable=True, comment="AI输出结果")
    status = db.Column(db.String(16), default="completed", comment="任务状态")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), comment="创建人ID")
    create_time = db.Column(db.DateTime, default=datetime.now, comment="创建时间")
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关联用户
    creator = db.relationship("User", backref="ai_tasks")


# 系统操作日志表
class SysOperationLog(db.Model):
    __tablename__ = "sys_operation_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, comment="操作用户ID（admin为超级管理员）")
    username = db.Column(db.String(50), nullable=False, comment="操作用户名")
    operation = db.Column(db.String(50), nullable=False, comment="操作类型：login/delete_user/change_role/add_case等")
    ip = db.Column(db.String(50), comment="操作IP地址")
    operate_time = db.Column(db.DateTime, default=datetime.now, comment="操作时间")
    detail = db.Column(db.Text, comment="操作详情（如：删除用户ID=1，修改角色为admin等）")
