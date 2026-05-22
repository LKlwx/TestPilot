# ADR-001: 用例模型统一抽象重构

## 状态

2026-05-22 · Accepted

## 上下文

当前项目中存在三个用例模型：`TestCase`（接口测试）、`UICase`（UI 自动化）、`PerformanceCase`（性能压测）。三者独立定义了以下字段的重复：

| 字段 | TestCase | UICase | PerformanceCase |
|------|----------|--------|-----------------|
| id | 有 | 有 | 有 |
| name | 有 | 有 | 有 |
| creator_id | 有 | 有 | 无 |
| create_time | 有 | 有 | 有 |
| update_time | 有 | 有 | 无 |

暴露的问题：
1. 公有字段在三处重复定义，新增字段或修改类型需要同步三处，容易遗漏
2. `PerformanceCase` 缺少 `creator_id` 和 `update_time`，审计追溯能力不足
3. 后续新增用例类型（如 WebSocketCase）会继续复制粘贴，累积技术债
4. 外键约束不完整（`PerformanceReport.case_id` 等缺少 ForeignKey，见 ADR-002）

## 可选方案对比

### 方案 A：STI（单表继承）

将三张表合并为一张大表 `case`，用 `type` 字段区分行所属类型。

优点：
- 单表查询简单

缺点：
- 大量 NULL 列：不同用例类型持有不同字段，表中稀疏
- 需要合并现有三张表的数据，迁移风险高
- SQLite 对稀疏表的存储效率低

结论：不采用。

### 方案 B：CTI（类表继承）

新建基类表 `base_case` 存放公有字段，三张子表只存特有字段，查询时 JOIN。

优点：
- 符合关系型数据库范式，无 NULL 列
- 基类字段修改只需改一处

缺点：
- 所有查询都需要 JOIN，增加开销
- 需要新建表 + 编写数据迁移脚本
- 现有 API 层大量使用 `TestCase.query.get(id)` 直接查询，迁移后需全部改写

结论：不采用。

### 方案 C：Mixin（独立抽象基类）

不改变数据库表结构，通过 Python 的 Mixin 机制在代码层面提取公有字段定义。

```
BaseCaseMixin（抽象类，不对应数据库表）
  id          = Column(Integer, primary_key)
  name        = Column(String(100))
  creator_id  = Column(Integer, ForeignKey("user.id"))
  create_time = Column(DateTime)
  update_time = Column(DateTime)

TestCase(BaseCaseMixin, db.Model)          → test_case（表结构不变）
UICase(BaseCaseMixin, db.Model)            → ui_case（表结构不变）
PerformanceCase(BaseCaseMixin, db.Model)   → performance_case（表结构不变）
```

优点：
- 零数据迁移：表结构完全不变，现有数据零影响
- 零 API 改动：字段名不变，所有 `TestCase.query` 等查询语法不变
- 公有字段修改只需改 Mixin 一处
- 新增用例类型只需继承 Mixin，无需重复定义公有字段
- 顺手修复 PerformanceCase 缺少 creator_id 和 update_time 的问题

缺点：
- 只在代码层面消除重复，数据库层面仍然是三张独立表（但三张独立表本身是合理的设计）

结论：采用。

## 决策

采用方案 C：Mixin（独立抽象基类）。

## 设计约束

以下字段虽然出现在多个模型中，但含义不同，**不抽取**到 Mixin 中：
- `url`：TestCase 中是 API 地址，UICase 中是页面地址
- `headers` / `body`：TestCase 中是接口请求参数，PerformanceCase 中是压测配置
- `method`：TestCase 中是 RESTful 方法，PerformanceCase 中是压测方法

## 影响范围

### 改动文件
- `models/base_case.py`（新建，定义 BaseCaseMixin）
- `models.py`（三个模型继承 Mixin，移除重复字段）

### 不改动文件
- 所有 API 路由（`api/test.py`、`api/ui.py`、`api/performance.py`）
- 所有 Service 层
- 数据库表结构

## 迁移方案

零迁移。Mixin 不改变表结构，启动即生效。

`PerformanceCase` 新增 `creator_id` 和 `update_time` 字段的处理：
- 开发/测试环境：`db.drop_all()` + `db.create_all()`
- 生产环境：手动执行 `ALTER TABLE performance_case ADD COLUMN creator_id INTEGER REFERENCES user(id)`；已有数据该字段为 NULL

## 回滚方案

删除 Mixin，将公有字段定义恢复为每个模型独立声明。表级无影响。
