from flask import Blueprint, request, render_template, session, redirect
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt

from core.exception import AuthException, NotFoundException, APIException
from core.response import success, error
from models import TestCase, UICase, TestReport, UIReport, User, PerformanceReport, SysOperationLog
from service.user_service import check_user_password
from extensions import db
from core.logger import get_logger
from core.schema import validate_request
from core.require_role import require_role
from api.schemas import LoginSchema, RegisterSchema, ChangePasswordSchema, ChangeRoleSchema
from service.operation_log_service import add_operation_log

logger = get_logger(__name__)

auth_bp = Blueprint("auth", __name__)


# 登录页面
@auth_bp.route("/login/page", methods=["GET"])
def login_page():
    return render_template("login.html")


@auth_bp.route("/page/home", methods=["GET"])
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



# 登录接口
@auth_bp.route("/login", methods=["POST"])
def login():
    data = validate_request(LoginSchema, request.get_json())
    username = data["username"]
    password = data["password"]

    from core.blocklist import is_login_locked, record_login_failure, reset_login_attempts
    from core.logger import get_logger
    username_key = username.strip().lower()
    if is_login_locked(username_key):
        get_logger(__name__).warning("登录失败（账号锁定）: %s", username_key)
        return error("用户名或密码错误")

    user = check_user_password(username, password)
    if not user:
        record_login_failure(username_key)
        return error("用户名或密码错误")

    reset_login_attempts(username_key)

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


@auth_bp.route("/logout", methods=["POST"])
@jwt_required(verify_type=False)
def logout():
    from flask_jwt_extended import get_jwt
    from core.blocklist import add_to_blocklist
    jti = get_jwt()["jti"]
    add_to_blocklist(jti)
    return success(msg="已登出")


@auth_bp.route("/user/<int:uid>/reset-password", methods=["POST"])
@require_role(["admin"])
def admin_reset_password(uid):
    from core.blocklist import reset_login_attempts
    target = User.query.get(uid)
    if not target:
        raise NotFoundException("用户不存在")
    default_pwd = "123456"
    target.set_password(default_pwd)
    reset_login_attempts(target.username)
    db.session.commit()
    identity = get_jwt_identity()
    current_user = User.query.get(int(identity))
    add_operation_log(current_user.id, current_user.username, "reset_password",
                      f"管理员重置用户{target.username}(ID={uid})的密码")
    return success(msg=f"用户 {target.username} 的密码已重置为默认密码")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = validate_request(RegisterSchema, request.get_json())
    import re
    username_clean = data["username"].strip().lower()
    
    if username_clean == "admin":
        return error("该用户名已被系统占用，无法注册")

    username_pattern = r'^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$'
    if not re.match(username_pattern, username_clean):
        return error("用户名只能包含字母、数字、下划线、中划线和中文")

    if User.query.filter_by(username=username_clean).first():
        return error("用户名已存在")

    new_user = User(username=username_clean)
    new_user.set_password(data["password"])
    new_user.role = "tester"

    db.session.add(new_user)
    db.session.commit()

    return success({}, "注册成功")


# 用户管理模块
# 获取所有用户列表
@auth_bp.route("/page/user/list", methods=["GET"])
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

    data = validate_request(ChangePasswordSchema, request.get_json())
    if not user.check_password(data["old_password"]):
        return error("当前密码错误")

    user.set_password(data["new_password"])
    db.session.commit()

    add_operation_log(user.id, user.username, "change_password", "用户修改密码")
    return success(msg="密码修改成功")


# 操作日志接口
@auth_bp.route("/operation/logs", methods=["GET"])
@require_role(["admin"])
def operation_logs():
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
@require_role(["admin"])
def cleanup_logs():
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=30)

    deleted = SysOperationLog.query.filter(SysOperationLog.operate_time < cutoff_date).delete()
    db.session.commit()

    return success(msg=f"已清理 {deleted} 条日志")


# 用户数据接口（返回JSON，带JWT）
@auth_bp.route("/user/list/data", methods=["GET"])
@require_role(["admin"])
def user_list_data():
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
    if not current_user or current_user.username != "admin":
        raise AuthException("无权限")

    data = validate_request(ChangeRoleSchema, request.get_json())
    user = User.query.get(data["id"])
    if not user:
        raise NotFoundException("用户不存在")

    old_role = user.role
    user.role = data["role"]
    db.session.commit()
    add_operation_log(current_user.id, current_user.username, "change_role", f"将用户{user.username}(ID={data['id']})从{old_role}修改为{data['role']}")
    return success(msg="角色修改成功")


# 删除用户
@auth_bp.route("/user/<int:uid>", methods=["DELETE"])
@require_role(["admin"])
def delete_user(uid):
    current_user = User.query.get(int(get_jwt_identity()))
    
    target = User.query.get(uid)
    if not target:
        raise NotFoundException("用户不存在")
    
    if current_user.username == "admin":
        add_operation_log(current_user.id, current_user.username, "delete_user", f"超级管理员删除用户{target.username}(ID={uid})")
        db.session.delete(target)
        db.session.commit()
        return success(msg="删除成功")
    
    if target.role != "tester":
        return error("普通管理员只能删除普通用户", 403)
    
    add_operation_log(current_user.id, current_user.username, "delete_user",
                      f"管理员{current_user.username}删除用户{target.username}(ID={uid})")
    db.session.delete(target)
    db.session.commit()
    return success(msg="删除成功")


# 数据统计大屏
@auth_bp.route("/dashboard/data", methods=["GET"])
@jwt_required()
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
            from sqlalchemy import func
            # 按 URL 聚合，取每个 URL 最慢的一次请求，按耗时降序取前 5 个
            top5_details = db.session.query(
                PerformanceDetail.url,
                func.max(PerformanceDetail.request_time).label('max_time')
            ).filter(
                PerformanceDetail.report_id == last_perf_report.id
            ).group_by(
                PerformanceDetail.url
            ).order_by(
                func.max(PerformanceDetail.request_time).desc()
            ).limit(5).all()
            
            for idx, d in enumerate(top5_details):
                url = d.url or "未知URL"
                perf_names.append(url[:30] + "..." if len(url) > 30 else url)
                perf_qps.append(round(last_perf_report.qps or 0, 1))
                perf_rt.append(round(d.max_time or 0, 1))
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
        logger.error("Dashboard Error: %s", str(e), exc_info=True)
        return error(str(e), 500)


# 测试接口（仅开发环境可用）
@auth_bp.route("/test/fast")
def test_fast():
    from flask import current_app
    if not current_app.config.get("DEBUG", False):
        from core.exception import NotFoundException
        raise NotFoundException("接口不存在")
    return success({"msg": "fast"})
