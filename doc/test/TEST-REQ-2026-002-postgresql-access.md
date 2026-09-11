# PostgreSQL 接入测试文档

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 测试编号 | TEST-REQ-2026-002 |
| 关联需求 | [REQ-2026-002-postgresql-access.md](../requirements/REQ-2026-002-postgresql-access.md) |
| 关联详细设计 | [DESIGN-REQ-2026-002-postgresql-access.md](../design/DESIGN-REQ-2026-002-postgresql-access.md) |
| 关联数据库设计 | [DB-REQ-2026-002-postgresql-access.md](../database/DB-REQ-2026-002-postgresql-access.md) |
| 文档版本 | 0.2 |
| 文档状态 | 执行中 |
| 测试负责人 | 待指定 |
| 测试日期 | 2026-09-11 |

## 2. 测试范围与依据

- 测试目标：验证 PostgreSQL 连接配置、`/ready` 成功与失败、`/health` 不变、Demo 删除、无业务表、敏感信息不泄露。
- 范围内：`GET /ready`、`GET /health`、`GET /`、Demo 路径删除、Settings `DATABASE_URL`、默认 pytest 的 Session 覆盖。
- 范围外：真实 PostgreSQL 长期联调（环境限制）、业务表 DDL、LLM 档案落库、认证权限、审计脱敏。
- 验收依据：REQ-2026-002 AC-001～AC-010、BR-001～BR-006、DESIGN-REQ-2026-002 验证计划。

## 3. 测试环境与准备

| 项目 | 内容 |
| --- | --- |
| 后端版本/提交 | 工作区当前实现；`uv run pytest` 于 2026-09-11 执行，36 passed |
| Python / uv | Python 3.12 / 项目 `uv.lock` |
| 数据库 | 默认 pytest 不连接真实 PostgreSQL；用依赖覆盖模拟 Session |
| 外部依赖 | 不调用真实 GPT |
| 目标服务 | FastAPI `TestClient` |
| 测试身份 | 公开接口，无登录 |
| 测试数据 | 无业务写入；无持久化清理对象 |

准备要求：不得使用生产数据库或记录真实连接串。默认测试拦截真实 Session。真实 `/ready` 200 需本地 PostgreSQL，未准备时标记未执行。

## 4. 测试用例

> 结果只使用：未执行、通过、失败、阻塞、不适用。

### TC-001 应用可启动并提供 Session 入口

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-001
- 测试层级：Route / Persistence
- 目标模块与入口：`app.db.session.get_session`、`Settings.database_url`
- 依赖：`tests/test_ready.py`、`tests/test_health.py`
- 前置条件：测试环境可导入应用
- 输入数据：使用配置中的示例 `DATABASE_URL` 格式，不断言真实凭据
- 步骤：
  1. 导入应用与 Settings。
  2. 检查存在 `database_url` 配置和 `get_session`。
  3. 使用 TestClient 访问 `/health`。
- 预期结果：
  - HTTP 状态：`/health` 200
  - 响应结构：原 `HealthResponse`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：Settings 含 `database_url`；`/health` 200
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_settings_has_database_url`、`tests/test_health.py`

### TC-002 数据库不可达时活性探针仍成功

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-002；REQ-003 / AC-005
- 测试层级：Route
- 目标模块与入口：`GET /health`
- 依赖：`tests/test_ready.py::test_health_ok_when_database_unavailable`
- 前置条件：`get_session` 覆盖为执行即失败
- 输入数据：无
- 步骤：
  1. 覆盖 Session 为失败实现。
  2. 访问 `/health`。
  3. 检查状态码和字段。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：`status=ok`，无 `database` 字段
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不因数据库失败而 5xx
- 清理：恢复依赖覆盖
- 实际结果：失败 Session 下 `/health` 仍 200，响应无 `database`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_health_ok_when_database_unavailable`

### TC-003 数据库可达时就绪探针成功

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-003
- 测试层级：Route
- 目标模块与入口：`GET /ready`
- 依赖：`tests/test_ready.py::test_ready_ok`
- 前置条件：默认假 Session 的 `execute` 成功
- 输入数据：无
- 步骤：
  1. 访问 `/ready`。
  2. 检查状态码、`status`、`database`。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：`status=ok`，`database=ok`，含 `app`、`version`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：假 Session 下 `/ready` 200，`status=ok`，`database=ok`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_ready_ok`。此为依赖覆盖，不是真实 PostgreSQL。

### TC-004 数据库不可达时就绪探针返回 503 且不泄露连接串

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-004；REQ-006 / AC-010
- 测试层级：Route
- 目标模块与入口：`GET /ready`
- 依赖：`tests/test_ready.py::test_ready_unavailable_does_not_leak_dsn`
- 前置条件：假 Session 在 `execute` 时抛出 `SQLAlchemyError`
- 输入数据：无
- 步骤：
  1. 覆盖失败 Session。
  2. 访问 `/ready`。
  3. 检查 503 与响应正文不含连接串、密码、`api_key`。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：`status=unavailable`，`database=unavailable`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：明确不可用，不是 200 空结果
- 清理：恢复依赖覆盖
- 实际结果：`/ready` 503，`status=unavailable`，`database=unavailable`，正文不含连接串
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_ready_unavailable_does_not_leak_dsn`

### TC-005 Demo 接口已删除

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-006、AC-007
- 测试层级：Route
- 目标模块与入口：`GET /api/v1/demo`、`POST /api/v1/demo`
- 依赖：`tests/test_ready.py::test_demo_routes_removed`
- 前置条件：服务已启动
- 输入数据：POST 使用原示例 JSON，仅用于确认不再创建
- 步骤：
  1. `GET /api/v1/demo`。
  2. `POST /api/v1/demo`。
  3. 静态确认无 `reset_demo_store`。
- 预期结果：
  - HTTP 状态：不再返回 200 列表或 201 创建
  - 响应结构：不是原 `DemoListResponse` / `DemoItem`
  - 数据、事务和缓存结果：无 Demo 存储
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：`GET/POST /api/v1/demo` 均为 404；`app.api.routes.demo` 模块不存在
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_demo_routes_removed`

### TC-006 无 LLM 密钥时根路径与活性探针可用

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-009
- 测试层级：Route
- 目标模块与入口：`GET /`、`GET /health`
- 依赖：`tests/test_llm.py::test_health_does_not_depend_on_llm_keys`、`tests/test_health.py`
- 前置条件：不注入 LLM 密钥
- 输入数据：无
- 步骤：
  1. 访问 `/` 与 `/health`。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：欢迎信息与原健康检查
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不因缺 LLM 密钥失败
- 清理：无
- 实际结果：`/` 与 `/health` 均为 200
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_health_does_not_depend_on_llm_keys`、`tests/test_health.py`

### TC-007 启动流程不建表且无业务 DDL

- 优先级：P0
- 关联需求/验收标准：REQ-005 / AC-008
- 测试层级：静态检查
- 目标模块与入口：`app/db/`、`doc/sql`、`app/main.py`
- 依赖：代码与目录检查
- 前置条件：当前工作区
- 输入数据：无
- 步骤：
  1. 确认无表模型、无 `create_all`、无 `doc/sql` 建表脚本。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：无业务表
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：无 `doc/sql/*.sql`，无 `app/db/models`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_no_business_sql_scripts`；静态检查 lifespan 无 `create_all`

### TC-008 真实 PostgreSQL 就绪探测

- 优先级：P1
- 关联需求/验收标准：REQ-002 / AC-003
- 测试层级：集成
- 目标模块与入口：`GET /ready` 对真实库
- 依赖：本地 Compose 或测试实例
- 前置条件：PostgreSQL 可达且 `DATABASE_URL` 指向该实例
- 输入数据：仅本地示例配置，不记录真实生产凭据
- 步骤：
  1. 启动 PostgreSQL。
  2. 配置 URL 后访问 `/ready`。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：`database=ok`
  - 数据、事务和缓存结果：无业务数据
  - 权限或依赖失败结果：不涉及
- 清理：停止本地实例；不删除未知数据库
- 实际结果：未准备真实 PostgreSQL，未执行
- 结果：未执行
- 证据/缺陷：环境限制；默认 pytest 不连真实库

## 5. 专项检查

- [x] 参数缺失、格式错误、资源不存在：Demo 删除后的 404。
- [ ] 未登录、无权限和越权访问：不涉及。
- [x] 重复请求、并发更新、写入回退和幂等：探针只读。
- [x] 外部调用正常、超时/失败及调用方处理：数据库失败转 503。
- [x] SQL 全量脚本、升级脚本、索引和逻辑删除：不涉及，已确认无脚本。
- [ ] 缓存命中、失效和数据一致性：不涉及。
- [x] 日志与响应不泄露敏感信息。

## 6. 验收覆盖矩阵

| 验收标准 | 测试用例 | 结果 | 说明 |
| --- | --- | --- | --- |
| AC-001 | TC-001 | 通过 | pytest |
| AC-002 | TC-002 | 通过 | pytest |
| AC-003 | TC-003 / TC-008 | 通过 / 未执行 | 假 Session 通过；真实库未执行 |
| AC-004 | TC-004 | 通过 | pytest |
| AC-005 | TC-002 | 通过 | pytest |
| AC-006 | TC-005 | 通过 | pytest |
| AC-007 | TC-005 | 通过 | pytest |
| AC-008 | TC-007 | 通过 | pytest + 静态检查 |
| AC-009 | TC-006 | 通过 | pytest |
| AC-010 | TC-004 | 通过 | pytest |

## 7. 缺陷与汇总

| 缺陷编号 | 关联用例 | 严重级别 | 描述 | 状态 |
| --- | --- | --- | --- | --- |
| - | - | - | 暂无 | - |

| 指标 | 数量 |
| --- | ---: |
| 用例总数 | 8 |
| 通过 | 7 |
| 失败 | 0 |
| 阻塞 | 0 |
| 不适用 | 0 |
| 未执行 | 1 |

- 测试结论：有条件通过
- 未完成项：TC-008 真实 PostgreSQL `/ready` 200
- 遗留风险：真实连通性依赖本地或测试实例；pytest 通过不等于数据库验收通过
- 数据清理结果：无业务写入；依赖覆盖在用例结束时清除

> pytest 36 passed 不能替代真实 PostgreSQL 验收。存在必要真实环境用例未执行，需求保持“开发中”。

## 8. 变更记录

| 日期 | 版本 | 变更内容 | 修改人 |
| --- | --- | --- | --- |
| 2026-09-11 | 0.1 | 初稿。 | 待指定 |
| 2026-09-11 | 0.2 | 记录隔离 pytest 结果；真实 PostgreSQL 联调标记未执行。 | 待指定 |
