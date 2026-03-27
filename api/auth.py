from flask import Blueprint, request, render_template, session, redirect
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from core.response import success, error
from models import TestCase, UICase, TestReport, UIReport, User, PerformanceReport, SysOperationLog
from service.user_service import check_user_password
from extensions import db

auth_bp = Blueprint("auth", __name__)


# 登录页面
@auth_bp.route("/login/page", methods=["GET"])
def login_page():
    return render_template("login.html")


@auth_bp.route("/home", methods=["GET"])
def home():
    return render_template("index.html")


# 控制台统计接口
@auth_bp.route("/stats", methods=["GET"])
def stats():
    # 1. 接口用例数
    api_count = TestCase.query.count()

    # 2. UI用例数
    ui_count = UICase.query.count()

    # 3. 总用例数
    total_count = api_count + ui_count

    # 4. 计算通过率（接口+UI报告）
    all_reports = list(TestReport.query.all()) + list(UIReport.query.all())
    total_reports = len(all_reports)
    pass_count = 0
    for r in all_reports:
        if r.status and r.status.upper() == "PASS":
            pass_count += 1

    pass_rate = 0
    if total_reports > 0:
        pass_rate = round(pass_count / total_reports * 100, 1)

    return success({
        "total_case": total_count,
        "api_case": api_count,
        "ui_case": ui_count,
        "pass_rate": f"{pass_rate}%"
    })


# 系统操作日志记录函数
def add_operation_log(user_id, username, operation, detail):
    log = SysOperationLog(
        user_id=user_id,
        username=username,
        operation=operation,
        ip=request.remote_addr,  # 自动获取操作IP
        detail=detail
    )
    db.session.add(log)
    db.session.commit()


# 登录接口
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return error("用户名或密码不能为空")

    if not username or not password:
        return error("用户名或密码不能为空")

    # 先判断写死的超级管理员
    if username == "admin" and password == "123456":
        token = create_access_token(identity="admin")
        return success({
            "token": token,
            "username": "admin",
            "role": "admin"
        }, "登录成功")

    # 再判断数据库用户
    user = check_user_password(username, password)
    if not user:
        return error("用户名或密码错误")

    token = create_access_token(identity=str(user.id))
    # 记录普通用户登录日志
    add_operation_log(user.id, user.username, "login", f"普通用户{username}登录系统")
    return success({
        "token": token,
        "username": user.username,
        "role": user.role
    }, "登录成功")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return error("用户名和密码不能为空")

    # 用户不能和超级管理员重名
    if username.lower() == "admin":
        return error("该用户名已被系统占用，无法注册")

    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return error("用户名已存在")

    # 新建用户（默认普通用户 tester）
    new_user = User(username=username)
    new_user.set_password(password)
    new_user.role = "tester"

    db.session.add(new_user)
    db.session.commit()

    return success({}, "注册成功")


# 用户管理模块
# 获取所有用户列表
@auth_bp.route("/user/list", methods=["GET"])
def user_list():
    return render_template("user_list.html")


# 用户数据接口（返回JSON，带JWT）
@auth_bp.route("/user/list/data", methods=["GET"])
@jwt_required()
def user_list_data():
    identity = get_jwt_identity()

    # 允许：超级管理员 + 数据库管理员
    allow = False
    if identity == "admin":
        allow = True
    else:
        u = User.query.get(identity)
        if u and u.role == "admin":
            allow = True
    if not allow:
        return error("无访问权限")

    users = User.query.all()
    res = []
    for u in users:
        if u.username == "admin":
            continue

        res.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "create_time": u.create_time.strftime("%Y-%m-%d %H:%M:%S") if u.create_time else ""
        })
    return success(res)


# 修改用户角色
@auth_bp.route("/user/role/change", methods=["POST"])
@jwt_required()
def change_user_role():
    identity = get_jwt_identity()

    # 只有超级管理员可以
    if identity != "admin":
        return error("无权限", 403)

    data = request.get_json()
    uid = data.get("id")
    role = data.get("role")

    if role not in ["admin", "tester"]:
        return error("角色不合法")

    user = User.query.get(uid)
    if not user:
        return error("用户不存在")

    old_role = user.role
    user.role = role
    db.session.commit()
    # 记录修改角色日志
    add_operation_log("admin", "admin", "change_role", f"将用户{user.username}(ID={uid})从{old_role}修改为{role}")
    return success(msg="角色修改成功")


# 删除用户
@auth_bp.route("/user/delete/<int:uid>", methods=["POST"])
@jwt_required()
def delete_user(uid):
    current_id = get_jwt_identity()

    # 1. 超级管理员（写死）随意删除
    if current_id == "admin":
        user = User.query.get(uid)
        if not user:
            return error("用户不存在")
        # 记录删除日志
        add_operation_log("admin", "admin", "delete_user", f"超级管理员删除用户{user.username}(ID={uid})")
        db.session.delete(user)
        db.session.commit()
        return success(msg="删除成功")

    # 2. 普通管理员只能删除用户
    admin_user = User.query.get(current_id)
    if not admin_user or admin_user.role != "admin":
        return error("无权限", 403)

    target = User.query.get(uid)
    if not target:
        return error("用户不存在")

    if target.role != "tester":
        return error("普通管理员只能删除普通用户", 403)
    # 记录删除日志
    add_operation_log(admin_user.id, admin_user.username, "delete_user",
                      f"管理员{admin_user.username}删除用户{target.username}(ID={uid})")
    db.session.delete(target)
    db.session.commit()
    return success(msg="删除成功")


# 数据统计大屏
@auth_bp.route("/dashboard/data", methods=["GET"])
def dashboard_data():
    from datetime import datetime, timedelta
    from models import PerformanceCase
    from sqlalchemy import func

    # 1. 用例统计（完全正常，你其他页面也是这么查的）
    api_count = TestCase.query.count()
    ui_count = UICase.query.count()
    perf_count = PerformanceCase.query.count()
    total_case = api_count + ui_count + perf_count

    # 2. 总通过率（去掉容易报错的 func.upper，改用原生判断，完全兼容你的SQLite）
    tr_list = TestReport.query.all()
    ui_list = UIReport.query.all()
    total_report = len(tr_list) + len(ui_list)
    pass_count_total = 0

    for r in tr_list:
        if r.status and 'PASS' in r.status.upper():
            pass_count_total += 1
    for r in ui_list:
        if r.status and 'PASS' in r.status.upper():
            pass_count_total += 1

    pass_rate = "0%"
    if total_report > 0:
        pass_rate = f"{round(pass_count_total / total_report * 100, 1)}%"

    # 3. 近7天通过率（完全改用你报告页面能用的朴素查询，100%兼容你的.db）
    today = datetime.now().date()
    days = []
    pass_trend = []

    for i in range(6, -1, -1):
        current_day = today - timedelta(days=i)
        days.append(current_day.strftime("%m-%d"))
        current_day_str = current_day.strftime("%Y-%m-%d")

        # 全表取出后再判断日期，你的报告页就是这么干的，一定能读到
        api_day_pass = 0
        api_day_total = 0
        for r in tr_list:
            ct = r.create_time
            if ct:
                if ct.strftime("%Y-%m-%d") == current_day_str:
                    api_day_total += 1
                    if r.status and 'PASS' in r.status.upper():
                        api_day_pass += 1

        ui_day_pass = 0
        ui_day_total = 0
        for r in ui_list:
            ct = r.create_time
            if ct:
                if ct.strftime("%Y-%m-%d") == current_day_str:
                    ui_day_total += 1
                    if r.status and 'PASS' in r.status.upper():
                        ui_day_pass += 1

        day_total = api_day_total + ui_day_total
        day_pass = api_day_pass + ui_day_pass
        day_rate = round(day_pass / day_total * 100, 1) if day_total > 0 else 0
        pass_trend.append(day_rate)

    # 4. 最近3次性能报告（你原来的代码唯一崩溃点：perf_rt = [] 删掉）
    perf_reports = PerformanceReport.query.order_by(PerformanceReport.id.desc()).limit(3).all()
    perf_names = []
    perf_qps = []
    perf_rt = []

    for p in perf_reports:
        try:
            name = p.case_name
            if len(name) > 8:
                name = name[:8] + "..."
            perf_names.append(name)
            perf_qps.append(round(p.qps or 0, 1))
            perf_rt.append(round(p.avg_time or 0, 1))
        except:
            perf_names.append("无数据")
            perf_qps.append(0)
            perf_rt.append(0)

    return success({
        "total_case": total_case,
        "api_case": api_count,
        "ui_case": ui_count,
        "perf_count": perf_count,
        "pass_rate": pass_rate,
        "days": days,
        "pass_trend": pass_trend,
        "perf_names": perf_names,
        "perf_qps": perf_qps,
        "perf_rt": perf_rt
    })


# 测试接口
@auth_bp.route("/test/fast")
def test_fast():
    return success({"msg": "fast"})
