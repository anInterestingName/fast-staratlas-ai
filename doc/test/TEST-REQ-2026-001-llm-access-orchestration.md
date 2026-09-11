# LLM 接入与编排基础能力测试文档

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 测试编号 | TEST-REQ-2026-001 |
| 关联需求 | [REQ-2026-001-llm-access-orchestration.md](../requirements/REQ-2026-001-llm-access-orchestration.md) |
| 关联详细设计 | [DESIGN-REQ-2026-001-llm-access-orchestration.md](../design/DESIGN-REQ-2026-001-llm-access-orchestration.md) |
| 关联数据库设计 | 不涉及 |
| 文档版本 | 0.4 |
| 文档状态 | 执行中 |
| 测试负责人 | 待指定 |
| 测试日期 | 2026-09-11 |

## 2. 测试范围与依据

- 测试目标：验证 LLM 档案列表、同步对话、SSE 流式对话、失败转移、配置隔离和密钥安全底线。
- 范围内：`GET /api/v1/llm/profiles`、`POST /api/v1/llm/chat`、`POST /api/v1/llm/chat/stream`、Settings 嵌套配置、Schema 白名单、现有 `/health` 回归。Demo 回归已由 REQ-2026-002 取消。
- 范围外：真实 GPT 计费联调（需外部密钥与网络）、结构化输出、档案 CRUD、数据库、认证权限、审计脱敏。
- 验收依据：REQ-2026-001 AC-001～AC-031、BR-001～BR-011、DESIGN-REQ-2026-001 验证计划与 DESIGN-ITEM-002/004。

## 3. 测试环境与准备

| 项目 | 内容 |
| --- | --- |
| 后端版本/提交 | 工作区未提交实现；`uv run pytest` 于 2026-09-11 执行 |
| Python / uv | Python 3.12.13 / 项目 `uv.lock`（含 `langchain-core`、`langchain-openai`） |
| 数据库 | 不涉及 |
| 外部依赖 | 默认 pytest 注入 fake ConfigProvider / fake Chat Model，不访问真实 GPT |
| 目标服务 | FastAPI `TestClient` |
| 测试身份 | 公开接口，无登录 |
| 测试数据 | 进程内假档案 `fast`/`smart`，密钥仅测试占位且不断言实值；无持久化写入 |

准备要求：LLM 测试通过依赖覆盖注入假配置和假模型；`conftest` 默认拦截真实 `ChatOpenAI` 工厂。不得使用生产密钥。

## 4. 测试用例

> 结果只使用：未执行、通过、失败、阻塞、不适用。

### TC-001 就绪档案列表不含密钥

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-001
- 测试层级：Route
- 目标模块与入口：`GET /api/v1/llm/profiles`
- 依赖：`tests/test_llm.py::test_list_profiles_ready_without_secrets`
- 前置条件：注入已就绪 `smart`/`fast` 档案
- 输入数据：无
- 步骤：
  1. 调用档案列表接口。
  2. 检查状态码、`smart` 就绪标记和字段白名单。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：含 `smart` 且 `ready=true`，字段仅 `name`/`ready`/`model`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：依赖覆盖在用例结束后清除
- 实际结果：响应含就绪 `smart`，无密钥字段
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-002 缺密钥档案标记未就绪

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-002
- 测试层级：Route / 配置
- 目标模块与入口：`GET /api/v1/llm/profiles`；`SettingsLLMConfigProvider`
- 依赖：`test_list_profiles_marks_missing_key_not_ready`、`test_settings_allow_empty_llm_keys`
- 前置条件：`fast` 或默认档案缺少密钥
- 输入数据：无
- 步骤：
  1. 将 `fast` 标为未就绪后请求列表。
  2. 使用空密钥 Settings 读取档案视图。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：对应档案 `ready=false`，无密钥
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：未就绪标记正确，空密钥档案 `ready=false`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-003 无密钥时健康检查可用

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-003；BR-003
- 测试层级：Route
- 目标模块与入口：`GET /health`
- 依赖：`test_health_does_not_depend_on_llm_keys`、`tests/test_health.py`
- 前置条件：不注入 LLM 密钥
- 输入数据：无
- 步骤：
  1. 访问 `/health`。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：健康检查 `status=ok`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不因缺 LLM 密钥失败
- 清理：无
- 实际结果：`/health` 200，`status=ok`；根路径 200
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_health_does_not_depend_on_llm_keys`、`tests/test_health.py`

### TC-004 配置中的模型名生效

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-025；REQ-002 / AC-006
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_uses_configured_model_name`
- 前置条件：将 `smart` 模型名改为 `gpt-4.1-mini`
- 输入数据：`{"messages":[{"role":"user","content":"hello"}]}`
- 步骤：
  1. 发起同样的对话请求。
  2. 检查 fake 工厂收到的模型名和请求路径。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：成功对话，路径仍为 `/api/v1/llm/chat`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：工厂记录模型名为新值
- 清理：无
- 实际结果：fake 模型收到 `gpt-4.1-mini`，路径未变
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-005 消息条数超上限不调用上游

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-026；BR-007
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_rejects_over_max_messages`
- 前置条件：档案 `max_messages=1`
- 输入数据：两条用户消息
- 步骤：
  1. 提交两条消息。
  2. 确认未创建上游模型。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：`detail.code=validation_error`
  - 数据、事务和缓存结果：无写入，上游调用次数为 0
  - 权限或依赖失败结果：不进入失败转移
- 清理：无
- 实际结果：422 且工厂 `created` 为空
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-006 请求禁止覆盖供应商配置

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-005；BR-001；BR-006
- 测试层级：Schema / Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_rejects_extra_override_fields`
- 前置条件：档案已就绪
- 输入数据：分别携带 `api_key` / `model` / `base_url` / `provider` / `think` / `think_level` / `key` / `url`
- 步骤：
  1. 提交带覆盖字段的请求。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：Pydantic 校验错误
  - 数据、事务和缓存结果：上游调用次数为 0
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：四类覆盖字段均 422，未调用上游
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-007 默认档案同步对话成功

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-004；REQ-003 / AC-007；REQ-010 / AC-028（隔离假上游）
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_default_profile_success`
- 前置条件：默认档案 `smart` 已就绪
- 输入数据：仅消息列表，不指定 `profile`
- 步骤：
  1. 提交合法用户消息。
  2. 检查响应字段白名单和用量。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：非空 `content`，`profile=smart`，可选 `usage`，无密钥
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：返回 `fake-assistant-reply` 与用量
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过。真实 GPT 见 TC-031。

### TC-008 指定 fast 档案

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-008
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_specified_fast_profile`
- 前置条件：`fast` 已就绪
- 输入数据：`profile=fast`
- 步骤：
  1. 提交合法对话。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：`profile=fast`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：工厂创建档案名为 `fast`
- 清理：无
- 实际结果：响应与工厂均为 `fast`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-009 空消息或非法角色被拒绝

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-009
- 测试层级：Schema
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_rejects_empty_or_invalid_messages`
- 前置条件：无
- 输入数据：空列表、非法 role、空白 content
- 步骤：
  1. 分别提交非法请求。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：校验错误
  - 数据、事务和缓存结果：上游调用次数为 0
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：三类非法输入均 422
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-010 SSE 流式成功

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-010
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat/stream`
- 依赖：`test_stream_success_has_delta_and_done`
- 前置条件：目标档案已就绪
- 输入数据：合法消息
- 步骤：
  1. 发起流式对话。
  2. 解析 SSE 事件。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：`Content-Type` 为 `text/event-stream`，至少一条非空 `delta`，并以 `done` 结束
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：收到 `Hel`/`lo` 两个 delta 和 `done`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-011 流式校验失败不升级为 SSE

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-011
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat/stream`
- 依赖：`test_stream_invalid_request_is_json_not_sse`
- 前置条件：无
- 输入数据：`messages=[]`
- 步骤：
  1. 发起非法流式请求。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：普通 JSON，`Content-Type` 不含 `text/event-stream`
  - 数据、事务和缓存结果：上游调用次数为 0
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：422 JSON，未开流
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-012 流式中途失败可区分

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-012
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat/stream`
- 依赖：`test_stream_midway_failure_sends_error`
- 前置条件：上游在发出增量后失败，无后续成功备用
- 输入数据：合法消息
- 步骤：
  1. 消费 SSE。
- 预期结果：
  - HTTP 状态：200（已进入 SSE）
  - 响应结构：有 `delta`，最后为 `event: error`，无 `done`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：调用方可区分未完成
- 清理：无
- 实际结果：末事件为 `error`，无 `done`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-013 主档案失败后转移到备用

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-015
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_fallback_to_ready_profile`
- 前置条件：`smart` 超时失败，`fast` 就绪且成功，`fallbacks=["fast"]`
- 输入数据：默认档案对话
- 步骤：
  1. 发起同步对话。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：`profile=fast`，非空内容
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：依次尝试 smart、fast
- 清理：无
- 实际结果：成功档案为 `fast`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-014 全部档案失败返回 503

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-016；BR-005
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_all_profiles_fail`
- 前置条件：主档案和备用均超时
- 输入数据：合法消息
- 步骤：
  1. 发起同步对话。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：`detail.code=upstream_timeout`，不是带空文本的 200
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：明确依赖失败
- 清理：无
- 实际结果：503，响应无成功 `content`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-015 校验失败不进入转移

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-017；BR-004
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_rejects_extra_override_fields`、`test_chat_rejects_over_max_messages`
- 前置条件：请求非法
- 输入数据：覆盖字段或超上限消息
- 步骤：
  1. 提交非法请求。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：校验错误
  - 数据、事务和缓存结果：上游次数为 0
  - 权限或依赖失败结果：不转移
- 清理：无
- 实际结果：未创建任何模型
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-016 服务端系统提示前置

- 优先级：P0
- 关联需求/验收标准：REQ-007 / AC-018
- 测试层级：编排
- 目标模块与入口：`ChatOrchestrator` via `POST /api/v1/llm/chat`
- 依赖：`test_chat_prepends_system_prompt`
- 前置条件：合法对话
- 输入数据：一条用户消息
- 步骤：
  1. 成功调用后检查发给模型的首条消息。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：成功文本
  - 数据、事务和缓存结果：发给模型的首条为配置中的 system prompt
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：首条为配置系统策略，其后为用户原文
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-017 超时映射为上游失败

- 优先级：P0
- 关联需求/验收标准：REQ-008 / AC-020
- 测试层级：Route / 工厂
- 目标模块与入口：`POST /api/v1/llm/chat`；`LangchainChatModelFactory`
- 依赖：`test_chat_timeout_maps_to_upstream_timeout`、`test_factory_passes_model_timeout_and_disables_retries`
- 前置条件：无备用；假上游抛出 `TimeoutError`；工厂使用档案超时且 `max_retries=0`
- 输入数据：合法消息
- 步骤：
  1. 发起同步对话。
  2. 检查工厂创建的 `ChatOpenAI` 超时与重试参数。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：`detail.code=upstream_timeout`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不一直挂起；SDK 重试关闭
- 清理：无
- 实际结果：503 `upstream_timeout`；工厂 `timeout=12`、`max_retries=0`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过。未对真实网络做 60 秒超时等待。

### TC-018 空内容不得当成功

- 优先级：P0
- 关联需求/验收标准：REQ-008 / AC-021
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_empty_content_is_not_success`
- 前置条件：上游返回空文本，备用同样为空
- 输入数据：合法消息
- 步骤：
  1. 发起同步对话。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：`detail.code=upstream_failed`
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：可区分非成功对话
- 清理：无
- 实际结果：503，不是 200 空文本
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-019 响应不含密钥

- 优先级：P0
- 关联需求/验收标准：REQ-009 / AC-022
- 测试层级：Route
- 目标模块与入口：全部 LLM 接口
- 依赖：各成功/失败用例中的 `assert_no_secrets`
- 前置条件：假档案含测试占位密钥
- 输入数据：成功与失败请求
- 步骤：
  1. 检查响应 JSON 序列化结果。
- 预期结果：
  - HTTP 状态：按各用例
  - 响应结构：不含 `api_key` 或占位密钥全文
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：失败体同样无密钥
- 清理：无
- 实际结果：响应中未出现密钥字段或占位密钥
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-020 失败日志只含档案名和错误类型

- 优先级：P0
- 关联需求/验收标准：REQ-009 / AC-023
- 测试层级：日志
- 目标模块与入口：`app.llm.orchestrator`
- 依赖：`test_failure_logs_profile_not_secrets`
- 前置条件：上游超时且无备用
- 输入数据：合法消息
- 步骤：
  1. 捕获 WARNING 日志。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：依赖失败
  - 数据、事务和缓存结果：日志含档案名和 `upstream_timeout`，不含密钥和完整消息
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：日志含 `smart` 与错误码，不含占位密钥和 `hello`
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-021 `.env.example` 仅占位密钥

- 优先级：P0
- 关联需求/验收标准：REQ-009 / AC-024
- 测试层级：静态检查
- 目标模块与入口：`.env.example`
- 依赖：`test_env_example_has_placeholder_keys_only`
- 前置条件：无
- 输入数据：文件内容
- 步骤：
  1. 读取 LLM 相关 `KEY` 行。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：值为空，无 `sk-` 实值
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：`LLM__FAST__KEY=` 与 `LLM__SMART__KEY=` 为空
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-022 无档案表和无 CRUD API

- 优先级：P0
- 关联需求/验收标准：REQ-010 / AC-027；BR-010
- 测试层级：静态检查 / Route
- 目标模块与入口：`/api/v1/llm/profiles` 写方法；`doc/sql`
- 依赖：`test_no_profile_write_routes`、`test_no_llm_sql_scripts`
- 前置条件：无
- 输入数据：POST/PUT/DELETE 档案
- 步骤：
  1. 调用写接口。
  2. 检查是否存在 LLM SQL。
- 预期结果：
  - HTTP 状态：404 或 405
  - 响应结构：无档案写入契约
  - 数据、事务和缓存结果：无 `doc/sql` LLM 脚本
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：写方法不被支持，无 LLM SQL
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-023 HTTP 契约无存储来源字段

- 优先级：P1
- 关联需求/验收标准：REQ-010 / AC-029
- 测试层级：Schema
- 目标模块与入口：`ChatRequest`、`ChatResponse`、`LLMProfileItem`
- 依赖：`test_response_models_have_no_storage_source_fields`
- 前置条件：无
- 输入数据：模型字段名
- 步骤：
  1. 检查 Schema 字段白名单。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：无 `api_key`/`base_url`/`provider`/`source`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：字段白名单符合设计
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-024 嵌套环境变量不破坏扁平配置

- 优先级：P1
- 关联需求/验收标准：DESIGN-ITEM-004
- 测试层级：配置
- 目标模块与入口：`Settings`
- 依赖：`test_nested_env_does_not_break_flat_settings`
- 前置条件：清理 LLM/APP 环境变量后写入 `APP_NAME` 与 `LLM__*`
- 输入数据：`LLM__DEFAULT=fast`、`LLM__FALLBACKS=["smart","fast"]`、`LLM__FAST__KEY` 等
- 步骤：
  1. 实例化 `Settings(_env_file=None)`。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：`app_name` 仍可读；`fallbacks` 解析为 JSON 列表；缺省仍含 `smart`
  - 权限或依赖失败结果：不涉及
- 清理：monkeypatch 恢复环境
- 实际结果：扁平变量与嵌套 LLM 配置同时生效
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-025 档案不存在返回 404

- 优先级：P1
- 关联需求/验收标准：EX-002
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_profile_not_found`
- 前置条件：无名为 `missing` 的档案
- 输入数据：`profile=missing`
- 步骤：
  1. 提交对话。
- 预期结果：
  - HTTP 状态：404
  - 响应结构：`detail.code=profile_not_found`
  - 数据、事务和缓存结果：不调用上游、不转移
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：404 且工厂为空
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-026 未就绪档案不走备用链

- 优先级：P0
- 关联需求/验收标准：EX-003；BR-002
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_profile_not_ready_does_not_fallback`
- 前置条件：默认 `smart` 未就绪，`fast` 就绪
- 输入数据：省略 profile
- 步骤：
  1. 提交对话。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：`detail.code=profile_not_ready`
  - 数据、事务和缓存结果：不调用上游
  - 权限或依赖失败结果：不因存在就绪备用而改打
- 清理：无
- 实际结果：503，工厂为空
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-027 单条长度超上限

- 优先级：P1
- 关联需求/验收标准：BR-007
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`test_chat_rejects_over_max_length`
- 前置条件：`max_length=3`
- 输入数据：`content=abcd`
- 步骤：
  1. 提交对话。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：校验错误
  - 数据、事务和缓存结果：上游次数为 0
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：422 且未调用上游
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-028 结构化输出接口

- 优先级：P2
- 关联需求/验收标准：REQ-005 / AC-013
- 测试层级：不适用
- 目标模块与入口：不适用
- 依赖：无
- 前置条件：本迭代移出范围
- 输入数据：不适用
- 步骤：
  1. 不实现、不验收结构化输出接口。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：不适用
  - 权限或依赖失败结果：不适用
- 清理：无
- 实际结果：编号保留，不作为完成条件
- 结果：不适用
- 证据/缺陷：无

### TC-029 结构化解析失败不得伪装成功

- 优先级：P2
- 关联需求/验收标准：REQ-005 / AC-014
- 测试层级：不适用
- 目标模块与入口：不适用
- 依赖：无
- 前置条件：本迭代移出范围
- 输入数据：不适用
- 步骤：
  1. 不执行。
- 预期结果：不适用
- 清理：无
- 实际结果：不适用
- 结果：不适用
- 证据/缺陷：无

### TC-030 结构化编排解析

- 优先级：P2
- 关联需求/验收标准：REQ-007 / AC-019
- 测试层级：不适用
- 目标模块与入口：不适用
- 依赖：无
- 前置条件：随 REQ-005 移出
- 输入数据：不适用
- 步骤：
  1. 不执行。
- 预期结果：不适用
- 清理：无
- 实际结果：不适用
- 结果：不适用
- 证据/缺陷：无

### TC-031 真实 GPT 联调

- 优先级：P0
- 关联需求/验收标准：REQ-010 / AC-028（真实密钥路径）
- 测试层级：集成
- 目标模块与入口：`POST /api/v1/llm/chat`、`POST /api/v1/llm/chat/stream`
- 依赖：外部 OpenAI 兼容 GPT、有效档案密钥、网络
- 前置条件：配置已就绪 `smart` 档案和真实密钥
- 输入数据：一条真实用户消息
- 步骤：
  1. 配置密钥后手工调用同步与流式接口。
  2. 确认非空助手文本和 SSE 增量。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：非空 `content` 或 SSE `delta`/`done`
  - 数据、事务和缓存结果：无本地持久化；上游按调用计费
  - 权限或依赖失败结果：密钥无效时应 503 而非空成功
- 清理：不保存对话；不把密钥写入仓库
- 实际结果：未执行。当前环境无获准的真实 GPT 密钥与网络联调。
- 结果：未执行
- 证据/缺陷：环境限制。隔离假上游路径已由 TC-007 覆盖。

### TC-032 思考参数映射到上游

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-030、AC-031；BR-011
- 测试层级：配置 / 工厂
- 目标模块与入口：`LangchainChatModelFactory`、`ChatRequest`
- 依赖：`test_factory_maps_think_to_reasoning_effort`、`test_factory_passes_model_timeout_and_disables_retries`、`test_chat_rejects_extra_override_fields`
- 前置条件：隔离工厂，不访问真实上游
- 输入数据：`think=true, think_level=high`；`think=false`；请求体携带 `think`
- 步骤：
  1. 用思考开启档案创建 `ChatOpenAI`。
  2. 用思考关闭档案创建 `ChatOpenAI`。
  3. 对话请求携带 `think`/`think_level`。
- 预期结果：
  - HTTP 状态：覆盖字段 422
  - 响应结构：不涉及成功体
  - 数据、事务和缓存结果：开启时 `reasoning_effort=high` 且不传 temperature；关闭时不传 `reasoning_effort`
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：工厂参数符合映射；请求覆盖被拒绝
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

## 5. 专项检查

- [x] 参数缺失、格式错误、资源不存在和非法状态。
- [x] 未登录、无权限和越权访问（如已纳入范围）。本需求不涉及认证，接口公开。
- [x] 重复请求、并发更新、写入回退和幂等。对话不幂等、无写入；未做压力并发。
- [x] 外部调用正常、超时/失败及调用方处理。假上游覆盖成功、超时、空内容和中途流失败。
- [x] SQL 全量脚本、升级脚本、索引和逻辑删除（如已纳入范围）。不涉及。
- [x] 缓存命中、失效和数据一致性（如已纳入范围）。不缓存模型输出。
- [x] 日志与响应不泄露敏感信息。

## 6. 验收覆盖矩阵

| 验收标准 | 测试用例 | 结果 | 说明 |
| --- | --- | --- | --- |
| AC-001 | TC-001 | 通过 | pytest |
| AC-002 | TC-002 | 通过 | pytest |
| AC-003 | TC-003 | 通过 | pytest：仅 `/health`，Demo 已删除 |
| AC-004 | TC-007 | 通过 | pytest |
| AC-005 | TC-006 | 通过 | pytest |
| AC-006 | TC-004 | 通过 | 只改配置模型名，路径不变 |
| AC-007 | TC-007 | 通过 | pytest |
| AC-008 | TC-008 | 通过 | pytest |
| AC-009 | TC-009 | 通过 | pytest |
| AC-010 | TC-010 | 通过 | pytest |
| AC-011 | TC-011 | 通过 | pytest |
| AC-012 | TC-012 | 通过 | pytest |
| AC-013 | TC-028 | 不适用 | 本迭代移出 |
| AC-014 | TC-029 | 不适用 | 本迭代移出 |
| AC-015 | TC-013 | 通过 | pytest |
| AC-016 | TC-014 | 通过 | pytest |
| AC-017 | TC-015 | 通过 | pytest |
| AC-018 | TC-016 | 通过 | pytest |
| AC-019 | TC-030 | 不适用 | 本迭代移出 |
| AC-020 | TC-017 | 通过 | 假超时；未做真实 60s 等待 |
| AC-021 | TC-018 | 通过 | pytest |
| AC-022 | TC-019 | 通过 | pytest |
| AC-023 | TC-020 | 通过 | pytest caplog |
| AC-024 | TC-021 | 通过 | 静态检查 |
| AC-025 | TC-004 | 通过 | pytest |
| AC-026 | TC-005 | 通过 | pytest |
| AC-027 | TC-022 | 通过 | pytest |
| AC-028 | TC-007 / TC-031 | 通过 / 未执行 | 假上游通过；真实 GPT 未执行 |
| AC-029 | TC-023 | 通过 | pytest |
| AC-030 | TC-032 / TC-006 | 通过 | pytest |
| AC-031 | TC-032 | 通过 | pytest |

## 7. 缺陷与汇总

| 缺陷编号 | 关联用例 | 严重级别 | 描述 | 状态 |
| --- | --- | --- | --- | --- |
| - | - | - | 暂无 | - |

| 指标 | 数量 |
| --- | ---: |
| 用例总数 | 32 |
| 通过 | 28 |
| 失败 | 0 |
| 阻塞 | 0 |
| 不适用 | 3 |
| 未执行 | 1 |

- 测试结论：有条件通过
- 未完成项：TC-031 真实 GPT 同步/流式联调
- 遗留风险：兼容供应商流式 chunk 形状可能不同；真实超时/限流需在有密钥环境复核
- 数据清理结果：无持久化数据；TestClient 与依赖覆盖已在用例结束时复位

> 当前全量 `uv run pytest` 40 passed，不能替代真实 GPT 验收。存在必要真实环境用例未执行，需求保持“开发中”。

## 8. 变更记录

| 日期 | 版本 | 变更内容 | 修改人 |
| --- | --- | --- | --- |
| 2026-09-11 | 0.1 | 初稿并记录隔离 pytest 结果；真实 GPT 联调标记未执行。 | 待指定 |
| 2026-09-11 | 0.2 | TC-003 去掉 Demo 回归，改由 REQ-2026-002 删除示例接口；health 用例待复核。 | 待指定 |
| 2026-09-11 | 0.3 | 随 REQ-2026-002 回归 pytest，TC-003 仅验证 `/health`，结果通过。 | 待指定 |
| 2026-09-11 | 0.4 | 配置字段缩短；新增 TC-032 覆盖 `think`/`think_level` 映射。 | 待指定 |
