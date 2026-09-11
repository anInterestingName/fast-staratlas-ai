# FastAPI 工程基线测试文档

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 测试编号 | TEST-REQ-2026-003 |
| 关联需求 | [REQ-2026-003-engineering-baseline.md](../requirements/REQ-2026-003-engineering-baseline.md) |
| 关联详细设计 | [DESIGN-REQ-2026-003-engineering-baseline.md](../design/DESIGN-REQ-2026-003-engineering-baseline.md) |
| 关联数据库设计 | 不涉及 |
| 文档版本 | 0.1 |
| 文档状态 | 执行中 |
| 测试负责人 | 待指定 |
| 测试日期 | 2026-09-11 |

## 2. 测试范围与依据

- 测试目标：验证 Ruff 检查入口、JSON 统一错误出口、未捕获 500、探针/SSE 兼容、日志级别与可开关 HTTP 访问日志。
- 范围内：`pyproject.toml` Ruff 配置、`GET /`、`GET /health`、`GET /ready`、LLM JSON/SSE 失败与成功体、`LOG_LEVEL`/`HTTP_LOG`、`.env.example`。
- 范围外：CI、类型检查、真实生产日志采集、真实 GPT 联调、审计/脱敏产品。
- 验收依据：REQ-2026-003 AC-001～AC-022、BR-001～BR-011、DESIGN-REQ-2026-003 验证计划。

## 3. 测试环境与准备

| 项目 | 内容 |
| --- | --- |
| 后端版本/提交 | 工作区当前实现；`uv run pytest` 于 2026-09-11 执行，59 passed；`uv run ruff check` 与 `uv run ruff format --check` 通过 |
| Python / uv | Python 3.12 / 项目 `uv.lock` |
| 数据库 | 默认 pytest 不连接真实 PostgreSQL；用依赖覆盖模拟 Session |
| 外部依赖 | 不调用真实 GPT；LLM 使用 `tests/llm_fakes.py` |
| 目标服务 | FastAPI `TestClient` |
| 测试身份 | 公开接口，无登录 |
| 测试数据 | 无业务写入；临时测试路由 `/__test/boom` 仅在用例内挂载并移除 |

准备要求：不得记录真实密钥、Token 或连接串。未捕获 500 使用 `raise_server_exceptions=False` 的 TestClient，避免 Starlette 在 handler 返回后再次抛出干扰断言。

## 4. 测试用例

> 结果只使用：未执行、通过、失败、阻塞、不适用。

### TC-001 Ruff 检查命令可用

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-001
- 测试层级：静态检查
- 目标模块与入口：`pyproject.toml`、`uv run ruff check`
- 依赖：开发依赖已安装
- 前置条件：已 `uv sync --group dev`
- 输入数据：仓库受管 Python
- 步骤：
  1. 执行 `uv run ruff check`。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：通过为零退出，违规为非零退出
- 清理：无
- 实际结果：命令可用，当前工作区零退出
- 结果：通过
- 证据/缺陷：`uv run ruff check`：All checks passed

### TC-002 受管代码通过检查与格式化检查

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-002
- 测试层级：静态检查
- 目标模块与入口：`app/`、`tests/`
- 依赖：TC-001
- 前置条件：当前工作区
- 输入数据：无
- 步骤：
  1. 执行 `uv run ruff check`。
  2. 执行 `uv run ruff format --check`。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：二者均零退出
- 清理：无
- 实际结果：检查与格式化检查均通过，52 files already formatted
- 结果：通过
- 证据/缺陷：`uv run ruff check`；`uv run ruff format --check`

### TC-003 开发依赖仅以 Ruff 为风格工具

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-003
- 测试层级：静态检查
- 目标模块与入口：`pyproject.toml`
- 依赖：`tests/test_errors.py::test_ruff_is_the_only_style_tool`
- 前置条件：当前工作区
- 输入数据：无
- 步骤：
  1. 读取 `pyproject.toml`。
  2. 确认存在 Ruff 开发依赖与 `[tool.ruff]`，且依赖声明不含 Black/isort/flake8 包。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：`ruff>=0.13` 与 `[tool.ruff]` 存在；依赖列表无 black/isort/flake8
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_ruff_is_the_only_style_tool`

### TC-004 档案不存在返回统一 404

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-004
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`tests/test_llm.py::test_chat_profile_not_found`
- 前置条件：假档案仅含 fast/smart
- 输入数据：`profile=missing`，消息 `hello`
- 步骤：
  1. 调用同步对话。
  2. 检查状态码与 `detail.code`/`message`。
- 预期结果：
  - HTTP 状态：404
  - 响应结构：`detail` 为对象，`code=profile_not_found`，message 为字符串
  - 数据、事务和缓存结果：无写入
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：404，`detail.code=profile_not_found`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_chat_profile_not_found`

### TC-005 上游失败返回既有 503 业务码

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-005
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`tests/test_llm.py::test_chat_timeout_maps_to_upstream_timeout`
- 前置条件：无备用档案，主档案超时
- 输入数据：默认档案对话
- 步骤：
  1. 注入超时。
  2. 调用同步对话。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：`detail.code` 为 `upstream_timeout` 或 `upstream_failed`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：明确失败，不是 200
- 清理：无
- 实际结果：503，`upstream_timeout`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_chat_timeout_maps_to_upstream_timeout`、`test_chat_all_profiles_fail`

### TC-006 成功体无统一信封

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-006
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`tests/test_llm.py::test_chat_default_profile_success`
- 前置条件：假模型成功
- 输入数据：消息 `hello`
- 步骤：
  1. 调用同步对话。
  2. 检查顶层字段。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：顶层 `profile`/`content`/`usage`，无 `data` 或业务 `code`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：200，字段仅为资源模型
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_chat_default_profile_success`

### TC-007 缺少 messages 返回对象形 422

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-011
- 测试层级：Route / Schema
- 目标模块与入口：`POST /api/v1/llm/chat`
- 依赖：`tests/test_errors.py::test_missing_messages_returns_validation_object`
- 前置条件：应用已启动
- 输入数据：空 JSON `{}`
- 步骤：
  1. 调用同步对话。
  2. 检查 `detail` 是否为对象。
- 预期结果：
  - HTTP 状态：422
  - 响应结构：`detail.code=validation_error`，存在 `message`，`detail` 不是数组
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：422，`detail` 为对象，`code=validation_error`，含精简 `errors`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_missing_messages_returns_validation_object`

### TC-008 未捕获异常返回泛化 500

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-007、AC-008；REQ-005 / AC-015
- 测试层级：Route
- 目标模块与入口：临时 `GET /__test/boom`
- 依赖：`tests/test_errors.py::test_unhandled_exception_returns_internal_error`
- 前置条件：测试内挂载抛 `RuntimeError("secret")` 的路由
- 输入数据：无
- 步骤：
  1. 挂载临时路由。
  2. 使用 `raise_server_exceptions=False` 的 TestClient 访问。
  3. 检查响应正文与日志。
- 预期结果：
  - HTTP 状态：500
  - 响应结构：`detail.code=internal_error`，泛化 message；无 traceback、无 `secret`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志可见 `RuntimeError`
- 清理：移除临时路由
- 实际结果：500 统一对象；正文无 secret/Traceback；日志含 `error_type=RuntimeError`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_unhandled_exception_returns_internal_error`

### TC-009 调试开关开启时 500 仍无堆栈

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-009
- 测试层级：Route
- 目标模块与入口：临时 `GET /__test/boom-debug`
- 依赖：`tests/test_errors.py::test_unhandled_exception_debug_still_hides_stack`
- 前置条件：`settings.debug=True`，FastAPI `debug=False`
- 输入数据：无
- 步骤：
  1. 打开调试配置。
  2. 触发未声明异常。
- 预期结果：
  - HTTP 状态：500
  - 响应结构：仍为泛化 `internal_error`，正文无堆栈
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：恢复 debug；移除临时路由
- 实际结果：正文仍无 secret/Traceback/RuntimeError
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_unhandled_exception_debug_still_hides_stack`

### TC-010 就绪失败保持探针模型

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-010
- 测试层级：Route
- 目标模块与入口：`GET /ready`
- 依赖：`tests/test_errors.py::test_ready_failure_keeps_probe_model`、`tests/test_ready.py`
- 前置条件：Session 执行失败
- 输入数据：无
- 步骤：
  1. 覆盖失败 Session。
  2. 访问 `/ready`。
- 预期结果：
  - HTTP 状态：503
  - 响应结构：含 `status`、`database`，无 `detail.code`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不进入 JSON 错误出口
- 清理：恢复依赖覆盖
- 实际结果：503，`status=unavailable`，无 `detail`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_ready_failure_keeps_probe_model`

### TC-011 流中失败发送 event error 且无 done

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-012
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat/stream`
- 依赖：`tests/test_llm.py::test_stream_midway_failure_sends_error`
- 前置条件：流式在首个 delta 后失败
- 输入数据：消息 `hello`
- 步骤：
  1. 调用流式对话。
  2. 解析 SSE 事件。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：最后有效事件名为 `error`，数据含 `code`/`message`，无随后 `done`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不改成 JSON 500
- 清理：无
- 实际结果：200 SSE，末事件 `error`，无 `done`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_stream_midway_failure_sends_error`

### TC-012 活性探针与根路径保持原 200

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-013；REQ-005 / AC-016
- 测试层级：Route
- 目标模块与入口：`GET /health`、`GET /`
- 依赖：`tests/test_errors.py::test_health_and_root_keep_success_shape`、`tests/test_health.py`
- 前置条件：默认配置，访问日志关闭
- 输入数据：无
- 步骤：
  1. 访问 `/health` 与 `/`。
- 预期结果：
  - HTTP 状态：均为 200
  - 响应结构：原 `HealthResponse` 与欢迎字典
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：`/health` 与 `/` 均为 200，形状未变
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_health_and_root_keep_success_shape`

### TC-013 领域错误日志不含对话正文

- 优先级：P0
- 关联需求/验收标准：REQ-005 / AC-014
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat`，logger `app.core.exception_handlers`
- 依赖：`tests/test_http_log.py::test_domain_error_logs_code_without_http_body`
- 前置条件：`HTTP_LOG=false`，档案不存在
- 输入数据：`profile=missing`，消息 `hello`
- 步骤：
  1. 关闭访问日志。
  2. 触发 `profile_not_found`。
  3. 检查日志。
- 预期结果：
  - HTTP 状态：404
  - 响应结构：统一错误对象
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志含错误码/异常类型，不含 api_key、连接串、hello
- 清理：无
- 实际结果：日志含 `profile_not_found` 与 `ProfileNotFoundError`，不含 hello 与测试密钥
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_domain_error_logs_code_without_http_body`

### TC-014 访问日志关闭时不打印业务正文

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-017
- 测试层级：Route
- 目标模块与入口：`HttpLogMiddleware`，`POST /api/v1/llm/chat`
- 依赖：`tests/test_http_log.py::test_http_log_disabled_omits_bodies`
- 前置条件：`http_log=False`
- 输入数据：消息 `hello`
- 步骤：
  1. 调用同步对话。
  2. 检查 `app.http` 日志。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：成功资源模型
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志无 hello 与助手正文
- 清理：无
- 实际结果：`app.http` 无 `http_request`，无消息/响应正文
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_http_log_disabled_omits_bodies`

### TC-015 访问日志打开时记录入参和响应

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-018
- 测试层级：Route
- 目标模块与入口：`HttpLogMiddleware`
- 依赖：`tests/test_http_log.py::test_http_log_enabled_records_request_and_response`
- 前置条件：`http_log=True`
- 输入数据：消息 `hello`
- 步骤：
  1. 打开开关。
  2. 调用同步对话。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：成功资源模型
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志含 method、path、hello、助手文本
- 清理：恢复开关
- 实际结果：日志含 `method=POST`、路径、hello、`fake-assistant-reply`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_http_log_enabled_records_request_and_response`

### TC-016 打开开关仍遮蔽密钥与 Authorization

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-019
- 测试层级：Route
- 目标模块与入口：`HttpLogMiddleware`
- 依赖：`tests/test_http_log.py::test_http_log_redacts_authorization_and_keys`
- 前置条件：`http_log=True`
- 输入数据：请求带 Authorization、X-API-Key 与 body `key`
- 步骤：
  1. 发送带密钥字段的 JSON 请求。
  2. 检查日志明文。
- 预期结果：
  - HTTP 状态：422（extra 字段非法）
  - 响应结构：统一校验错误
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志无 Authorization/密钥明文，敏感键为 `***`
- 清理：恢复开关
- 实际结果：明文密钥未出现；`key` 与 authorization 记为 `***`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_http_log_redacts_authorization_and_keys`

### TC-017 探针对访问日志不打印正文

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-020
- 测试层级：Route
- 目标模块与入口：`GET /health`、`GET /ready`
- 依赖：`tests/test_http_log.py::test_http_log_skips_probe_bodies`
- 前置条件：`http_log=True`
- 输入数据：无
- 步骤：
  1. 打开开关后访问探针。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：原探针模型
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：`app.http` 无探针正文
- 清理：恢复开关
- 实际结果：无 `http_request`，无探针 JSON 正文
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_http_log_skips_probe_bodies`

### TC-018 SSE 不逐条记录 delta

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-021
- 测试层级：Route
- 目标模块与入口：`POST /api/v1/llm/chat/stream`
- 依赖：`tests/test_http_log.py::test_http_log_sse_does_not_record_deltas`
- 前置条件：`http_log=True`，流式产生 `Hel`/`lo` 两段
- 输入数据：消息 `hello`
- 步骤：
  1. 调用流式对话。
  2. 检查访问日志。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：SSE
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志含 stream=start/end，不含增量 `Hel`
- 清理：恢复开关
- 实际结果：有 `stream=start`/`stream=end`，无 `Hel` 与 `event: delta`
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_http_log_sse_does_not_record_deltas`

### TC-019 配置示例标明访问日志默认关闭

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-022
- 测试层级：静态检查
- 目标模块与入口：`.env.example`
- 依赖：`tests/test_http_log.py::test_env_example_documents_http_log_and_log_level`
- 前置条件：当前工作区
- 输入数据：无
- 步骤：
  1. 读取 `.env.example`。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：能发现 `HTTP_LOG=false` 与开发/生产说明，以及 `LOG_LEVEL`
- 清理：无
- 实际结果：含 `LOG_LEVEL=INFO`、`HTTP_LOG=false` 及开发/生产注释
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_env_example_documents_http_log_and_log_level`

### TC-020 未注册路径与方法不允许也是统一对象

- 优先级：P1
- 关联需求/验收标准：REQ-002 / BR-002
- 测试层级：Route
- 目标模块与入口：未注册路径、`GET /api/v1/llm/chat`
- 依赖：`tests/test_errors.py::test_unregistered_path_returns_not_found_object`、`test_method_not_allowed_returns_object`
- 前置条件：应用已启动
- 输入数据：无
- 步骤：
  1. 访问不存在路径。
  2. 以 GET 调用仅 POST 的对话接口。
- 预期结果：
  - HTTP 状态：404 / 405
  - 响应结构：`not_found` / `method_not_allowed` 对象，不是字符串 `detail`
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：不涉及
- 清理：无
- 实际结果：404 `not_found`，405 `method_not_allowed`
- 结果：通过
- 证据/缺陷：`uv run pytest`：上述两个用例

### TC-021 过长正文截断

- 优先级：P1
- 关联需求/验收标准：REQ-006 / EX-010
- 测试层级：Route
- 目标模块与入口：`HttpLogMiddleware`
- 依赖：`tests/test_http_log.py::test_http_log_truncates_long_body`
- 前置条件：`http_log=True`
- 输入数据：5000 字符消息
- 步骤：
  1. 发送超长消息。
  2. 检查日志截断标记。
- 预期结果：
  - HTTP 状态：200
  - 响应结构：成功资源模型
  - 数据、事务和缓存结果：无
  - 权限或依赖失败结果：日志含 `...<truncated>`，不含完整超长正文
- 清理：恢复开关
- 实际结果：日志含截断标记，不含完整 5000 字符
- 结果：通过
- 证据/缺陷：`uv run pytest`：`test_http_log_truncates_long_body`

### TC-022 CI 与生产日志采集

- 优先级：P2
- 关联需求/验收标准：范围外
- 测试层级：不适用
- 目标模块与入口：不适用
- 依赖：无
- 前置条件：无
- 输入数据：无
- 步骤：
  1. 确认本需求不建设 CI 与集中式日志。
- 预期结果：
  - HTTP 状态：不适用
  - 响应结构：不适用
  - 数据、事务和缓存结果：不适用
  - 权限或依赖失败结果：不适用
- 清理：无
- 实际结果：明确不在本需求范围
- 结果：不适用
- 证据/缺陷：需求非目标

## 5. 专项检查

- [x] 参数缺失、格式错误、资源不存在：422 对象、404 对象、405 对象。
- [ ] 未登录、无权限和越权访问：不涉及。
- [x] 重复请求、并发更新、写入回退和幂等：检查命令与只读探针可重复。
- [x] 外部调用正常、超时/失败及调用方处理：LLM 上游 503 业务码保持。
- [x] SQL 全量脚本、升级脚本、索引和逻辑删除：不涉及。
- [ ] 缓存命中、失效和数据一致性：不涉及。
- [x] 日志与响应不泄露敏感信息。

## 6. 验收覆盖矩阵

| 验收标准 | 测试用例 | 结果 | 说明 |
| --- | --- | --- | --- |
| AC-001 | TC-001 | 通过 | `uv run ruff check` |
| AC-002 | TC-002 | 通过 | check + format --check |
| AC-003 | TC-003 | 通过 | pytest |
| AC-004 | TC-004 | 通过 | pytest |
| AC-005 | TC-005 | 通过 | pytest |
| AC-006 | TC-006 | 通过 | pytest |
| AC-007 | TC-008 | 通过 | pytest |
| AC-008 | TC-008 | 通过 | pytest |
| AC-009 | TC-009 | 通过 | pytest |
| AC-010 | TC-010 | 通过 | pytest |
| AC-011 | TC-007 | 通过 | pytest |
| AC-012 | TC-011 | 通过 | pytest |
| AC-013 | TC-012 | 通过 | pytest |
| AC-014 | TC-013 | 通过 | pytest |
| AC-015 | TC-008 | 通过 | pytest |
| AC-016 | TC-012 | 通过 | pytest |
| AC-017 | TC-014 | 通过 | pytest |
| AC-018 | TC-015 | 通过 | pytest |
| AC-019 | TC-016 | 通过 | pytest |
| AC-020 | TC-017 | 通过 | pytest |
| AC-021 | TC-018 | 通过 | pytest |
| AC-022 | TC-019 | 通过 | pytest |

## 7. 缺陷与汇总

| 缺陷编号 | 关联用例 | 严重级别 | 描述 | 状态 |
| --- | --- | --- | --- | --- |
| - | - | - | 暂无 | - |

| 指标 | 数量 |
| --- | ---: |
| 用例总数 | 22 |
| 通过 | 21 |
| 失败 | 0 |
| 阻塞 | 0 |
| 不适用 | 1 |
| 未执行 | 0 |

- 测试结论：有条件通过
- 未完成项：无必须的未执行用例；CI 与生产日志采集不在范围
- 遗留风险：Schema 422 从数组改为对象，依赖 FastAPI 默认校验体的客户端需同步；`HTTP_LOG=true` 会把对话正文写入进程日志
- 数据清理结果：无业务写入；临时路由在用例结束时移除；依赖覆盖由 conftest 清除

> pytest 59 passed 与 Ruff 通过不能替代生产日志与人工验收。OpenAPI 默认 422 schema 可能仍显示数组，运行时以 handler 为准。

## 8. 变更记录

| 日期 | 版本 | 变更内容 | 修改人 |
| --- | --- | --- | --- |
| 2026-09-11 | 0.1 | 初稿并记录隔离 pytest、Ruff 检查结果。 | 待指定 |
