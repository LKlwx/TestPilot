from flask import Blueprint, request, render_template, session, redirect
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt

from core.exception import AuthException, NotFoundException, APIException
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

    # 统一通过数据库校验
    user = check_user_password(username, password)
    if not user:
        return error("用户名或密码错误")

    # 生成双Token：Access Token（短期）+ Refresh Token（长期）
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    # 记录普通用户登录日志
    add_operation_log(user.id, user.username, "login", f"用户{username}登录系统")
    return success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "username": user.username,
        "role": user.role
    }, "登录成功")


# 刷新Token接口（无感刷新）
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """使用Refresh Token换取新的Access Token"""
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return error("用户不存在")
    
    # 生成新的Access Token
    new_access_token = create_access_token(identity=str(user.id))
    
    return success({
        "access_token": new_access_token,
        "username": user.username,
        "role": user.role
    }, "Token刷新成功")


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


# 个人中心页面
@auth_bp.route("/profile/page", methods=["GET"])
def profile_page():
    return render_template("profile.html")


# 操作日志页面
@auth_bp.route("/operation/logs/page", methods=["GET"])
def operation_logs_page():
    return render_template("operation_log.html")


# 获取当前用户信息
@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return error("用户不存在")
    return success({
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "create_time": user.create_time.strftime("%Y-%m-%d %H:%M") if user.create_time else "-"
    })


# 修改密码
@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return error("用户不存在")

    data = request.get_json()
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return error("密码不能为空")

    if not user.check_password(old_password):
        return error("当前密码错误")

    if len(new_password) < 6:
        return error("新密码长度不能少于6位")

    user.set_password(new_password)
    db.session.commit()

    add_operation_log(user.id, user.username, "change_password", "用户修改密码")
    return success(msg="密码修改成功")


# 操作日志接口
@auth_bp.route("/operation/logs", methods=["GET"])
@jwt_required()
def operation_logs():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user or user.role != "admin":
        return error("无访问权限")

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    keyword = request.args.get("keyword", "", type=str)
    date = request.args.get("date", "", type=str)

    query = SysOperationLog.query
    if keyword:
        query = query.filter(
            (SysOperationLog.username.like(f"%{keyword}%")) |
            (SysOperationLog.operation.like(f"%{keyword}%"))
        )
    if date:
        from datetime import datetime
        search_date = datetime.strptime(date, "%Y-%m-%d")
        from datetime import timedelta
        next_day = search_date + timedelta(days=1)
        query = query.filter(
            SysOperationLog.operate_time >= search_date,
            SysOperationLog.operate_time < next_day
        )

    total = query.count()
    logs = query.order_by(SysOperationLog.operate_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return success({
        "list": [{
            "id": log.id,
            "username": log.username,
            "operation": log.operation,
            "detail": log.detail,
            "ip": log.ip or "-",
            "operate_time": log.operate_time.strftime("%Y-%m-%d %H:%M:%S") if log.operate_time else "-"
        } for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })


# 清理旧日志
@auth_bp.route("/operation/logs/cleanup", methods=["POST"])
@jwt_required()
def cleanup_logs():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user or user.role != "admin":
        return error("无访问权限")

    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=30)

    deleted = SysOperationLog.query.filter(SysOperationLog.operate_time < cutoff_date).delete()
    db.session.commit()

    return success(msg=f"已清理 {deleted} 条日志")


# 用户数据接口（返回JSON，带JWT）
@auth_bp.route("/user/list/data", methods=["GET"])
@jwt_required()
def user_list_data():
    identity = get_jwt_identity()
    current_user = User.query.get(int(identity))
    
    # 允许：超级管理员 + 普通管理员
    if not current_user or current_user.role != "admin":
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
    current_user = User.query.get(int(identity))
    
    # 只有超级管理员（username == "admin"）可以修改用户权限
    if not current_user or current_user.username != "admin":
        raise AuthException("无权限")

    data = request.get_json()
    uid = data.get("id")
    role = data.get("role")

    if role not in ["admin", "tester"]:
        raise APIException("角色不合法", 400)

    user = User.query.get(uid)
    if not user:
        raise NotFoundException("用户不存在")

    old_role = user.role
    user.role = role
    db.session.commit()
    # 记录修改角色日志
    add_operation_log(current_user.id, current_user.username, "change_role", f"将用户{user.username}(ID={uid})从{old_role}修改为{role}")
    return success(msg="角色修改成功")


# 删除用户
@auth_bp.route("/user/delete/<int:uid>", methods=["POST"])
@jwt_required()
def delete_user(uid):
    identity = get_jwt_identity()
    current_user = User.query.get(int(identity))
    
    if not current_user:
        raise AuthException("无权限")
    
    target = User.query.get(uid)
    if not target:
        raise NotFoundException("用户不存在")
    
    # 超级管理员可以删除任何人
    if current_user.username == "admin":
        add_operation_log(current_user.id, current_user.username, "delete_user", f"超级管理员删除用户{target.username}(ID={uid})")
        db.session.delete(target)
        db.session.commit()
        return success(msg="删除成功")
    
    # 普通管理员只能删除普通用户
    if current_user.role != "admin":
        raise AuthException("无权限")
    
    if target.role != "tester":
        return error("普通管理员只能删除普通用户", 403)
    
    add_operation_log(current_user.id, current_user.username, "delete_user",
                      f"管理员{current_user.username}删除用户{target.username}(ID={uid})")
    db.session.delete(target)
    db.session.commit()
    return success(msg="删除成功")


# 数据统计大屏
@auth_bp.route("/dashboard/data", methods=["GET"])
def dashboard_data():
    import traceback
    from datetime import datetime, timedelta
    from models import PerformanceCase
    from sqlalchemy import func

    try:
        # 1. 用例统计（增加性能用例）
        api_count = TestCase.query.count()
        ui_count = UICase.query.count()
        perf_count = PerformanceCase.query.count()
        total_case = api_count + ui_count + perf_count

        # 2. 今日执行分布（体现代码活跃度）
        today_start = datetime.combine(datetime.now().date(), datetime.min.time())
        today_api_run = db.session.query(func.count(TestReport.id)).filter(
            TestReport.create_time >= today_start
        ).scalar() or 0
        today_ui_run = db.session.query(func.count(UIReport.id)).filter(
            UIReport.create_time >= today_start
        ).scalar() or 0
        
        # 3. 近7天缺陷发现趋势（更有价值的指标）
        today = datetime.now().date()
        days = []
        fail_trend = []

        for i in range(6, -1, -1):
            current_day = today - timedelta(days=i)
            days.append(current_day.strftime("%m-%d"))
            current_day_start = datetime.combine(current_day, datetime.min.time())
            current_day_end = datetime.combine(current_day, datetime.max.time())

            api_fail = db.session.query(func.count(TestReport.id)).filter(
                TestReport.create_time >= current_day_start,
                TestReport.create_time <= current_day_end,
                TestReport.status != 'PASS'
            ).scalar() or 0
            ui_fail = db.session.query(func.count(UIReport.id)).filter(
                UIReport.create_time >= current_day_start,
                UIReport.create_time <= current_day_end,
                UIReport.status != 'PASS'
            ).scalar() or 0

            fail_trend.append(api_fail + ui_fail)

        # 4. 最近一次压测的慢接口 Top 5
        last_perf_report = PerformanceReport.query.order_by(PerformanceReport.id.desc()).first()
        perf_names = []
        perf_qps = []
        perf_rt = []

        if last_perf_report:
            from models import PerformanceDetail
            # 查询该报告关联的明细，按耗时降序取前 5 个
            top5_details = PerformanceDetail.query.filter_by(
                report_id=last_perf_report.id
            ).order_by(PerformanceDetail.request_time.desc()).limit(5).all()
            
            for idx, d in enumerate(top5_details):
                perf_names.append(f"请求 {idx + 1}")
                perf_qps.append(round(last_perf_report.qps or 0, 1))
                perf_rt.append(round(d.request_time or 0, 1))
        else:
            perf_names.append("暂无压测")
            perf_qps.append(0)
            perf_rt.append(0)

        return success({
            "total_case": total_case,
            "api_case": api_count,
            "ui_case": ui_count,
            "perf_count": perf_count,
            "today_api_run": today_api_run,
            "today_ui_run": today_ui_run,
            "days": days,
            "fail_trend": fail_trend,
            "perf_names": perf_names,
            "perf_qps": perf_qps,
            "perf_rt": perf_rt
        })
    except Exception as e:
        print("Dashboard Error:", str(e))
        print(traceback.format_exc())
        return error(str(e), 500)


# 测试接口
@auth_bp.route("/test/fast")
def test_fast():
    return success({"msg": "fast"})
