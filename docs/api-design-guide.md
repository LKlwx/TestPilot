# API 设计规范指南

> 制定时间：Phase 1.6  
> 适用范围：`api/` 下所有蓝图的路由定义

---

## 1. 路由命名规范

### 规则一：页面路由统一以 `/page` 开头

仅返回 `render_template` 的路由，路径中必须包含 `/page`：

```python
# 正确
@auth_bp.route("/page/home")
@auth_bp.route("/page/user/list")
@test_bp.route("/page/reports")

# 错误
@auth_bp.route("/home")
@auth_bp.route("/user/list")
@test_bp.route("/reports")
```

### 规则二：数据接口不包含 `/page`

返回 JSON 统一响应 `{code, msg, data}` 的路由，路径中不应包含 `/page`：

```python
# 正确
@auth_bp.route("/login")
@auth_bp.route("/user/list/data")
@test_bp.route("/reports/data")

# 错误
@auth_bp.route("/page/login")
```

### 规则三：GET 页面 / POST 数据 同主题共存时

使用 `route/data` 后缀区分：

```python
@auth_bp.route("/page/user/list")       # 页面路由
@auth_bp.route("/user/list/data")        # 数据接口
```

---

## 2. 响应格式规范

### 成功响应

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": { ... }
}
```

### 错误响应

```json
{
  "code": 400,
  "msg": "参数错误描述",
  "data": null
}
```

---

## 3. HTTP 状态码语义化

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | 成功 | 正常返回 |
| 400 | 参数错误 | 请求参数校验失败 |
| 401 | 未登录 | JWT Token 缺失或过期 |
| 403 | 权限不足 | 用户无此操作权限 |
| 404 | 资源不存在 | 请求的资源/接口未找到 |
| 500 | 服务器内部错误 | 未捕获的系统异常 |

> 注意：`success()` 和 `error()` 封装在 `core/response.py` 中，所有路由必须通过这两个函数返回 JSON，禁止直接 `jsonify()`。
