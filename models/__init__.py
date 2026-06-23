from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models.base_case import BaseCaseMixin


# ------------------------------
# 用户表（登录、权限）
# ------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(100), unique=True)
    role = db.Column(db.String(20), default="tester", index=True)  # admin/tester
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系回引
    test_cases = db.relationship("TestCase", backref="creator", lazy="dynamic")
    ui_cases = db.relationship("UICase", backref="creator", lazy="dynamic")
    performance_cases = db.relationship("PerformanceCase", backref="creator", lazy="dynamic")
    test_tasks = db.relationship("TestTask", backref="creator", lazy="dynamic")
    async_tasks = db.relationship("AsyncTask", backref="creator", lazy="dynamic")
    batch_tasks = db.relationship("BatchTask", backref="creator", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ------------------------------
# 测试用例表
# ------------------------------
class TestCase(BaseCaseMixin, db.Model):
    __tablename__ = "test_case"
    module = db.Column(db.String(50), default="默认模块", index=True, comment="所属模块")
    method = db.Column(db.String(10), nullable=False)  # GET/POST/PUT/DELETE
    url = db.Column(db.String(500), nullable=False)
    headers = db.Column(db.Text, default="{}")
    body = db.Column(db.Text, default="{}")
    expect = db.Column(db.String(200))  # 预期结果关键字
    extract_var = db.Column(db.String(200), comment="后置提取：格式如 token=$.args.token")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    timeout = db.Column(db.Integer, default=10, comment="请求超时时间（秒）")
    retry = db.Column(db.Integer, default=0, comment="失败重试次数")
    unstable = db.Column(db.Boolean, default=False, comment="不稳定用例标记：近5次执行中FLAKY>=3次")

    # 关系回引
    reports = db.relationship("TestReport", backref="case", lazy="dynamic")


# ------------------------------
# 测试报告表
# ------------------------------
class TestReport(db.Model):
    __tablename__ = "test_report"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("test_case.id", ondelete="CASCADE"), index=True)
    case_name = db.Column(db.String(100))
    status = db.Column(db.String(20), index=True)  # pass/fail/error/flaky
    retried = db.Column(db.Integer, default=0, comment="重试次数，0 表示第一次通过")
    cost_time = db.Column(db.Float)  # 耗时（秒）
    response_code = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    error_msg = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.now, index=True)


# ------------------------------
# 定时任务表
# ------------------------------

task_case_association = db.Table(
    "task_case_association",
    db.Column("task_id", db.Integer, db.ForeignKey("test_task.id", ondelete="CASCADE"), primary_key=True),
    db.Column("case_id", db.Integer, db.ForeignKey("test_case.id", ondelete="CASCADE"), primary_key=True),
)


class TestTask(db.Model):
    __tablename__ = "test_task"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    cron_expr = db.Column(db.String(50))  # 定时表达式，如 "0 0 * * *"
    status = db.Column(db.String(20), default="enabled")  # enabled/disabled
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    create_time = db.Column(db.DateTime, default=datetime.now)

    cases = db.relationship("TestCase", secondary=task_case_association, lazy="dynamic",
                            backref=db.backref("tasks", lazy="dynamic"))


# ------------------------------
# UI 自动化用例表
# ------------------------------
class UICase(BaseCaseMixin, db.Model):
    __tablename__ = "ui_case"
    url = db.Column(db.String(500), nullable=False)
    steps = db.Column(db.Text)  # 操作步骤
    loc_type = db.Column(db.String(20), default="xpath", comment="元素定位方式：id/xpath/css")
    loc_value = db.Column(db.String(500), comment="元素定位值")
    screenshot_path = db.Column(db.String(500), comment="测试截图路径")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系回引
    reports = db.relationship("UIReport", backref="case", lazy="dynamic")


# ------------------------------
# UI 自动化测试报告表
# ------------------------------
class UIReport(db.Model):
    __tablename__ = "ui_report"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("ui_case.id", ondelete="CASCADE"), index=True)
    case_name = db.Column(db.String(100))
    status = db.Column(db.String(20), index=True)  # pass/fail/error
    cost_time = db.Column(db.Float)
    error_msg = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.now, index=True)


# 性能测试用例表：存储压测的地址、并发、请求总数等配置
class PerformanceCase(BaseCaseMixin, db.Model):
    __tablename__ = "performance_case"
    url = db.Column(db.String(500), nullable=False)  # 压测URL
    method = db.Column(db.String(10), default="GET")  # 请求方法
    headers = db.Column(db.Text, default="{}")  # 请求头
    body = db.Column(db.Text)  # 请求体
    concurrency = db.Column(db.Integer, default=10)  # 目标并发数
    total = db.Column(db.Integer, default=50)  # 总请求次数
    ramp_steps = db.Column(db.Integer, default=1, comment="阶梯加压步数（1=直接加压，5=分5步到达目标并发）")
    steady_duration = db.Column(db.Integer, default=0, comment="稳态持续时间（秒，0=不持久化）")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系回引
    reports = db.relationship("PerformanceReport", backref="case", lazy="dynamic")


# 性能测试报告表：存储每次压测的结果数据
class PerformanceReport(db.Model):
    __tablename__ = "performance_report"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("performance_case.id", ondelete="CASCADE"), index=True)  # 对应的用例ID
    case_name = db.Column(db.String(100))  # 用例名称
    concurrency = db.Column(db.Integer)  # 并发数
    total = db.Column(db.Integer)  # 总请求数
    success = db.Column(db.Integer)  # 成功次数
    fail = db.Column(db.Integer)  # 失败次数
    qps = db.Column(db.Float)  # 每秒请求数
    avg_time = db.Column(db.Float)  # 平均响应时间(ms)
    min_time = db.Column(db.Float)  # 最小响应时间(ms)
    max_time = db.Column(db.Float)  # 最大响应时间(ms)
    create_time = db.Column(db.DateTime, default=datetime.now, index=True)
    p90 = db.Column(db.Float, default=0)
    p99 = db.Column(db.Float, default=0)
    success_rate = db.Column(db.Float, default=0)
    is_local = db.Column(db.Boolean, default=False, comment="是否本机压测（可能导致数据失真）")
    extra = db.Column(db.Text, nullable=True, comment="扩展数据（JSON，如每秒QPS序列）")

    # 关系回引
    details = db.relationship("PerformanceDetail", backref="report", lazy="dynamic")


# 性能测试明细表：存储每次请求的详细耗时，用于分析慢接口
class PerformanceDetail(db.Model):
    __tablename__ = "performance_detail"
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("performance_report.id", ondelete="CASCADE"), index=True, comment="关联压测报告ID")
    url = db.Column(db.String(500), comment="请求URL")
    request_time = db.Column(db.Float, comment="本次请求耗时(ms)")
    status_code = db.Column(db.Integer, comment="HTTP 状态码")
    create_time = db.Column(db.DateTime, default=datetime.now)


# 性能基线表：存储每次压测的基准值，用于对比判定性能退化
class PerformanceBaseline(db.Model):
    __tablename__ = "performance_baseline"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("performance_case.id", ondelete="CASCADE"), index=True, comment="关联用例ID")
    report_id = db.Column(db.Integer, db.ForeignKey("performance_report.id", ondelete="SET NULL"), comment="基线来源报告ID")
    p90 = db.Column(db.Float, comment="基线 P90（主判据）")
    p99 = db.Column(db.Float, comment="基线 P99")
    avg_time = db.Column(db.Float, comment="基线平均耗时")
    qps = db.Column(db.Float, comment="基线 QPS")
    create_time = db.Column(db.DateTime, default=datetime.now, comment="基线创建时间")
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment="基线更新时间")


# AI 智能测试任务记录表
class AIAgentTask(db.Model):
    __tablename__ = "ai_agent_task"

    id = db.Column(db.Integer, primary_key=True, comment="主键ID")
    # 任务类型：generate_api=生成接口用例 generate_ui=生成UI用例 analyze_failure=失败分析 summarize_report=报告总结
    task_type = db.Column(db.String(32), nullable=False, index=True, comment="任务类型")
    input_content = db.Column(db.Text, nullable=False, comment="用户输入内容")
    output_result = db.Column(db.Text, nullable=True, comment="AI输出结果")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True, comment="创建人ID")
    create_time = db.Column(db.DateTime, default=datetime.now, comment="创建时间")
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关联用户
    creator = db.relationship("User", backref="ai_tasks")


# Celery 异步任务表
class AsyncTask(db.Model):
    __tablename__ = "async_task"

    id = db.Column(db.String(36), primary_key=True)  # UUID
    task_type = db.Column(db.String(32), nullable=False, comment="任务类型: ai_generate / batch_run / ui_run / perf_run")
    status = db.Column(db.String(16), default="pending", index=True, comment="pending / running / success / failed")
    result = db.Column(db.Text, nullable=True, comment="任务结果（JSON）")
    error_msg = db.Column(db.Text, nullable=True, comment="错误信息")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True, comment="创建者ID")
    create_time = db.Column(db.DateTime, default=datetime.now, comment="创建时间")
    finish_time = db.Column(db.DateTime, nullable=True, comment="完成时间")


# 批量执行任务表
class BatchTask(db.Model):
    __tablename__ = "batch_task"
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Integer, default=0, comment="总用例数")
    passed = db.Column(db.Integer, default=0, comment="通过数")
    failed = db.Column(db.Integer, default=0, comment="失败数")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), comment="创建者")
    create_time = db.Column(db.DateTime, default=datetime.now, comment="创建时间")
    results = db.relationship("BatchResult", backref="batch", lazy="dynamic")


# 批量执行明细表
class BatchResult(db.Model):
    __tablename__ = "batch_result"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batch_task.id"), comment="所属批次")
    case_id = db.Column(db.Integer, db.ForeignKey("test_case.id", ondelete="CASCADE"), comment="用例ID")
    case_name = db.Column(db.String(100), comment="用例名称")
    status = db.Column(db.String(20), comment="pass / fail / error")
    cost_time = db.Column(db.Float, comment="耗时（秒）")
    response_code = db.Column(db.Integer, comment="响应状态码")
    error_msg = db.Column(db.Text, comment="错误信息")


# 系统操作日志表
class SysOperationLog(db.Model):
    __tablename__ = "sys_operation_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True, comment="操作用户ID（admin为超级管理员）")
    username = db.Column(db.String(50), nullable=False, comment="操作用户名")
    operation = db.Column(db.String(50), nullable=False, index=True, comment="操作类型：login/delete_user/change_role/add_case等")
    ip = db.Column(db.String(50), comment="操作IP地址")
    operate_time = db.Column(db.DateTime, default=datetime.now, index=True, comment="操作时间")
    detail = db.Column(db.Text, comment="操作详情（如：删除用户ID=1，修改角色为admin等）")


# 接口覆盖率统计表
class ApiCoverage(db.Model):
    __tablename__ = "api_coverage"
    id = db.Column(db.Integer, primary_key=True)
    method = db.Column(db.String(10), nullable=False, comment="HTTP 方法")
    path = db.Column(db.String(500), nullable=False, index=True, comment="URL 路径")
    summary = db.Column(db.String(200), nullable=True, comment="接口描述（从 Swagger 导入）")
    is_covered = db.Column(db.Boolean, default=False, index=True, comment="是否有测试覆盖")
    covered_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, comment="最后覆盖人")
    covered_time = db.Column(db.DateTime, nullable=True, comment="最后覆盖时间")
    create_time = db.Column(db.DateTime, default=datetime.now, comment="导入时间")


# 测试数据集（数据驱动）
class TestDataSet(db.Model):
    __tablename__ = "test_data_set"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment="数据集名称，如'注册-边界值'")
    case_id = db.Column(db.Integer, db.ForeignKey("test_case.id", ondelete="CASCADE"), index=True, comment="绑定的用例模板")
    data_rows = db.Column(db.Text, comment="数据行，JSON 数组，如 [{\"username\":\"a\",\"pwd\":\"1\"}]")
    create_time = db.Column(db.DateTime, default=datetime.now)

    case = db.relationship("TestCase", backref=db.backref("data_sets", lazy="dynamic"))
