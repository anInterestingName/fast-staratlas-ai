# PostgreSQL 接入详细设计

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 设计编号 | DESIGN-REQ-2026-002 |
| 关联需求 | [REQ-2026-002-postgresql-access.md](../requirements/REQ-2026-002-postgresql-access.md) |
| 关联数据库设计 | [DB-REQ-2026-002-postgresql-access.md](../database/DB-REQ-2026-002-postgresql-access.md) |
| 关联测试文档 | [TEST-REQ-2026-002-postgresql-access.md](../test/TEST-REQ-2026-002-postgresql-access.md) |
| 文档版本 | 0.2 |
| 文档状态 | 开发中 |
| 技术负责人 | 待指定 |
| 创建/更新日期 | 2026-09-11 |

## 2. 设计摘要

### 2.1 目标

1. 用 SQLAlchemy 2.0 + psycopg3 接入 PostgreSQL，提供引擎、Session 依赖和生命周期释放。
2. 新增 `GET /ready` 执行 `SELECT 1`；保持 `GET /health` 原契约。
3. 删除 Demo 示例接口、Schema、内存存储和测试，避免示例 CRUD 被当成落库对象。

### 2.2 非目标

- 不引入 SQLModel/Repository/Unit of Work 等无表抽象。
- 不创建业务表，不在启动时 `create_all` 或跑迁移。
- 不把 LLM 配置改为读库。
- 默认 pytest 不连接真实 PostgreSQL。

### 2.3 需求映射

| 需求/验收标准 | 设计落点 | 验证方式 |
| --- | --- | --- |
| REQ-001 / AC-001 | `Settings.database_url`、`app/db/session.py`、`get_session` | pytest：应用可导入并覆盖 Session |
| REQ-001 / AC-002 | 启动不连库；`/health` 不使用 Session | pytest：不注入真实库时 `/health` 200 |
| REQ-002 / AC-003 | `GET /ready` + `ping_database` | pytest：假 Session 成功路径 200 |
| REQ-002 / AC-004 | `/ready` 捕获 `SQLAlchemyError` 返回 503 | pytest：假 Session 失败路径 503，响应无连接串 |
| REQ-003 / AC-005 | `GET /health` 保持 `HealthResponse` | pytest：字段与接入前一致 |
| REQ-004 / AC-006、AC-007 | 删除 demo 路由/Schema/测试 | pytest：Demo 路径不再返回原契约；代码无 `reset_demo_store` |
| REQ-005 / AC-008 | 无 `doc/sql` DDL、无表模型、lifespan 不建表 | 静态检查 |
| REQ-006 / AC-009、AC-010 | LLM 仍读 Settings；探针响应无密钥/连接串 | pytest：无密钥时 `/`、`/health` 200；`/ready` 正文无敏感字段 |

## 3. 改动范围

| 层次 | 模块/路径 | 主要改动 |
| --- | --- | --- |
| 应用入口 | `app/main.py` | 增加 lifespan，进程结束时 `engine.dispose()` |
| 路由 | `app/api/routes/health.py`、`app/api/router.py` | 新增 `/ready`；移除 Demo 路由 |
| Schema | `app/schemas/health.py`、`app/schemas/__init__.py` | 新增 `ReadyResponse`；删除 Demo Schema |
| 配置 | `app/core/config.py`、`.env.example` | 新增 `database_url` / `DATABASE_URL` |
| 数据访问 | `app/db/session.py` | 新建引擎、Session、`ping_database` |
| 数据 | `doc/sql` | 不涉及建表 |
| 依赖 | `pyproject.toml` | 增加 `sqlalchemy`、`psycopg[binary]` |
| 测试 | `tests/conftest.py`、`tests/test_ready.py`、删除 `tests/test_demo.py` | 默认覆盖 Session；就绪成功/失败；删除 Demo 用例 |
| 调用方 | Demo 客户端 | 原 `/api/v1/demo` 不再提供；LLM 契约不变 |
| 文档 | REQ-2026-001 关联文档 | Demo 回归改为 `/` 与 `/health` |

## 4. 架构与流程

### 4.1 架构图

```mermaid
flowchart LR
    Client[调用方] --> FastAPI[FastAPI App]
    FastAPI --> Health["/health"]
    FastAPI --> Ready["/ready"]
    FastAPI --> LLM["/api/v1/llm"]
    Ready --> Session[get_session]
    Session --> Engine[SQLAlchemy Engine]
    Engine --> PG[(PostgreSQL)]
    LLM --> Provider[SettingsLLMConfigProvider]
    Provider --> Env[环境变量]
```

### 4.2 关键时序图

```mermaid
sequenceDiagram
    participant C as 调用方
    participant R as ready 路由
    participant S as Session
    participant E as PostgreSQL

    C->>R: GET /ready
    R->>S: ping_database SELECT 1
    alt 数据库可达
        S->>E: SELECT 1
        E-->>S: 1
        R-->>C: 200 ReadyResponse database=ok
    else 数据库不可达
        S-->>R: SQLAlchemyError
        R-->>C: 503 ReadyResponse database=unavailable
    end
```

### 4.3 主要流程

1. 导入配置，创建引擎（惰性连接，启动不强制 `SELECT 1`）。
2. `/health` 只读 Settings 中的应用名和版本。
3. `/ready` 注入 Session，执行 `SELECT 1`；成功 200，`SQLAlchemyError` 则 503。
4. 进程退出时 dispose 引擎。

## 5. 模块设计

### 5.1 Schema

| 类型 | 名称 | 职责 |
| --- | --- | --- |
| 响应模型 | `HealthResponse` | 活性探针，字段保持 `status`/`app`/`version` |
| 响应模型 | `ReadyResponse` | 就绪探针，增加 `database` |

### 5.2 路由与处理

| 类型 | 名称 | 职责 |
| --- | --- | --- |
| Router | `health.router` | `/health`、`/ready`，无 `/api/v1` 前缀 |
| 处理函数 | `ready` | 调用 `ping_database`，转换连通性错误为 503 |
| 存储 | `get_session` | 请求级 Session；本迭代无业务写入，不在依赖中自动 commit |

### 5.3 核心规则

| 规则 | 实现位置 | 失败行为 |
| --- | --- | --- |
| 活性探针不探库 | `health()` | 不获取 Session |
| 就绪失败不泄露连接串 | `ready()` | 503，固定 `unavailable`，日志只记“检查失败” |
| 无业务写入 | Session 依赖 | `finally: session.close()`，不 commit |
| Demo 删除 | 移除 `demo` 路由 | 框架 404 |

## 6. HTTP API 契约

| 方法 | 路径 | 权限/身份 | 请求 | 响应 | 幂等/并发 |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | 公开 | 无 | `HealthResponse` 200 | 只读，不探库 |
| GET | `/ready` | 公开 | 无 | `ReadyResponse` 200 / 503 | 只读探测 |
| GET/POST | `/api/v1/demo*` | 已删除 | 不适用 | 不再提供原契约 | 不适用 |

接口补充：

- `/ready` 成功：`{"status":"ok","app":"...","version":"...","database":"ok"}`
- `/ready` 失败：HTTP 503，`status=unavailable`，`database=unavailable`
- `/health` 不增加 `database` 字段
- 兼容策略：`/health`、`/`、LLM 保持；Demo 为刻意删除
- 敏感字段：响应禁止出现 URL、密码、`api_key`

## 7. 外部调用

不涉及业务外部 HTTP。PostgreSQL 是基础设施依赖，超时使用驱动/引擎默认值；失败由 `/ready` 转为 503，不得把空结果当成就绪。

## 8. 数据设计

- 数据库设计：[DB-REQ-2026-002-postgresql-access.md](../database/DB-REQ-2026-002-postgresql-access.md)
- 存储方式：PostgreSQL 16（建议版本，待指定确认）
- 持久化边界：本迭代无业务表、无写入、无逻辑删除
- 唯一约束和索引：不涉及
- 全量及升级脚本：不涉及

## 9. 事务、并发与缓存

| 主题 | 设计 |
| --- | --- |
| 本地写入边界 | 无业务写入；`/ready` 的 `SELECT 1` 不提交业务数据 |
| 跨服务事务 | 不涉及 |
| 并发控制 | 不涉及业务并发 |
| 幂等 | `/health`、`/ready` 只读，重复请求无副作用 |
| 缓存 | 不涉及 |

## 10. 认证与访问控制

- 认证方式：不涉及
- 操作权限：公开探针
- 数据归属：不涉及
- 敏感数据：`DATABASE_URL` 仅配置；响应和常规日志不得输出完整 URL 或密码

## 11. 异常与日志

| 场景 | 处理 | 对外结果 | 数据影响 |
| --- | --- | --- | --- |
| `/health` | 不连库 | 200 `HealthResponse` | 不改变 |
| 数据库可达 | `SELECT 1` 成功 | 200 `ReadyResponse` | 不改变 |
| 数据库不可达 | 捕获 `SQLAlchemyError` | 503 `ReadyResponse` | 不改变 |
| Demo 路径 | 路由已删除 | 404 | 不改变 |
| 配置非法 | Settings 校验失败，进程起不来 | 启动失败 | 不改变 |

日志使用固定文案记录就绪失败，不把异常字符串中的连接串写进响应。

## 12. 配置、发布与回滚

- 配置项：
  - `database_url` / `DATABASE_URL`
  - 本地示例默认值：`postgresql+psycopg://staratlas:staratlas@127.0.0.1:5432/fast_staratlas_ai`
  - 该默认值仅用于本地开发示例，不是生产凭据
- 可选本地依赖：`compose.yaml` 启动 PostgreSQL 16，账号与示例 URL 一致
- 发布顺序：准备 PostgreSQL 实例 → 配置 `DATABASE_URL` → 发布应用 → 用 `/health` 与 `/ready` 验证
- 兼容窗口：新版本删除 Demo；依赖 Demo 的调用方必须先下线
- 回滚顺序：回滚应用即可恢复旧 Demo 内存接口；本迭代未改库结构，数据库无需回滚
- 不可逆事项：Demo 删除是产品契约变化；代码回滚可恢复示例接口

## 13. 验证计划

- 依赖与测试：`uv sync --group dev`，`uv run pytest`。
- 静态检查：无 demo 路由/存储；无业务表模型；`/health` 签名不变；`DATABASE_URL` 进入 `.env.example`。
- 测试：
  - 默认覆盖 `get_session`，不连接真实库
  - `/ready` 成功与失败
  - `/health` 在失败覆盖下仍 200
  - Demo 路径不再返回原契约
  - 无 LLM 密钥时 `/` 与 `/health` 可用
- 真实 PostgreSQL 的 `/ready` 200 作为环境限制项，不以 pytest 覆盖代替。

## 14. 风险、评审与变更

| 编号 | 风险/问题 | 负责人 | 状态/结论 |
| --- | --- | --- | --- |
| DESIGN-ITEM-001 | 真实连通性依赖外部 Postgres 进程 | 待指定 | 开放：默认测试用假 Session |
| DESIGN-ITEM-002 | 导入时创建引擎可能让无驱动环境失败 | 待指定 | 已选 `psycopg[binary]`，create_engine 惰性连接 |
| DESIGN-ITEM-003 | REQ-2026-001 文档仍写 Demo 回归 | 待指定 | 同步修改 001 兼容说明 |

| 评审领域 | 结论 | 评审人 | 日期 |
| --- | --- | --- | --- |
| 后端/API | 待评审 | 待指定 | 待指定 |
| 数据库 | 待评审 | 待指定 | 待指定 |
| 测试可行性 | 待评审 | 待指定 | 待指定 |

| 日期 | 版本 | 变更内容 | 修改人 |
| --- | --- | --- | --- |
| 2026-09-11 | 0.1 | 初稿。连接层、`/ready`、删除 Demo、无业务表。 | 待指定 |
| 2026-09-11 | 0.2 | 记录实现完成范围、隔离 pytest 与未执行的真实 PostgreSQL 探测。 | 待指定 |

## 15. 实现完成记录

开发完成，待验收。

- 实际完成范围：`Settings.database_url`、SQLAlchemy 引擎与 `get_session`、`GET /ready`、保持 `GET /health`、删除 Demo 路由/Schema/测试、本地 `compose.yaml` 示例、隔离 pytest。
- 设计偏差：无。因本迭代无表，未引入 SQLModel。
- 已执行验证：`uv run pytest`，36 passed。
- 未执行项：真实 PostgreSQL 上的 `/ready` 200（TC-008）。
- 环境限制：默认测试覆盖 Session，不连接真实库。
- 待验收项：本地 Compose 启动 PostgreSQL 后手工访问 `/ready`；评审需求/设计确认。
