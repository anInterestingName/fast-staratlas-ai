# LLM 完整配置项与文件 CRUD 测试文档

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 测试编号 | TEST-REQ-2026-004 |
| 关联需求 | [REQ-2026-004-llm-config-store.md](../requirements/REQ-2026-004-llm-config-store.md) |
| 关联详细设计 | [DESIGN-REQ-2026-004-llm-config-store.md](../design/DESIGN-REQ-2026-004-llm-config-store.md) |
| 关联数据库设计 | 不涉及 |
| 文档版本 | 0.1 |
| 文档状态 | 执行中 |
| 测试负责人 | 待指定 |
| 测试日期 | 2026-09-11 |

## 2. 测试范围与依据

- 测试目标：验证 YAML 完整配置项、CRUD、请求 `config`/`fallback`、对话与图像分流、密钥不回显。
- 范围内：`/api/v1/llm/configs`、`/chat`、`/chat/stream`、`/images/generate`、`/images/edit`、假上游。
- 范围外：真实 OpenAI/Anthropic 联调、多实例文件一致性、认证。
- 验收依据：REQ-2026-004 AC-001～AC-015。

## 3. 测试环境与准备

| 项目 | 内容 |
| --- | --- |
| 后端版本/提交 | 工作区实现；`uv run pytest` 于 2026-09-11 执行 |
| Python / uv | Python 3.12 / 项目 `uv.lock` |
| 数据库 | 不涉及 |
| 外部依赖 | pytest 注入假配置与假模型，不访问真实上游 |
| 目标服务 | FastAPI `TestClient` |
| 测试身份 | 公开接口 |
| 测试数据 | 临时 YAML 与内存假配置，密钥为测试占位 |

## 4. 测试用例

### TC-001 两条配置凭据独立

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-001
- 测试层级：存储
- 目标模块与入口：`YamlConfigStore`
- 依赖：`test_yaml_store_keeps_independent_credentials`
- 前置条件：临时 YAML
- 输入数据：两条不同 baseurl/apikey
- 步骤：1. 创建两条配置 2. 分别读取
- 预期结果：地址与密钥互不相同
- 清理：临时目录
- 实际结果：两条配置独立
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-002 缺密钥未就绪

- 优先级：P0
- 关联需求/验收标准：REQ-001 / AC-002
- 依赖：`test_yaml_store_empty_key_not_ready`、`test_list_configs_marks_missing_key_not_ready`
- 前置条件：apikey 为空
- 步骤：创建或列表
- 预期结果：`ready=false`，无明文密钥
- 清理：无
- 实际结果：未就绪且无密钥字段
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-003 创建配置

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-003
- 依赖：`test_crud_create_get_update_delete`
- 步骤：POST `/api/v1/llm/configs`
- 预期结果：201，无 `apikey`，可再 GET
- 清理：用例内 DELETE
- 实际结果：201 且脱敏
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-004 重名创建

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-004
- 依赖：`test_crud_create_get_update_delete`
- 步骤：同名 POST 两次
- 预期结果：第二次 409 `config_exists`
- 清理：用例内删除
- 实际结果：409
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-005 PUT 省略密钥保留

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-005
- 依赖：`test_update_omits_apikey_keeps_secret`、`test_crud_create_get_update_delete`
- 步骤：更新时不传 apikey
- 预期结果：`has_key=true`，原密钥仍在存储
- 清理：临时文件
- 实际结果：密钥保留
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-006 删除后 404

- 优先级：P0
- 关联需求/验收标准：REQ-002 / AC-006
- 依赖：`test_crud_create_get_update_delete`
- 步骤：DELETE 后再 GET
- 预期结果：404 `config_not_found`
- 清理：无
- 实际结果：404
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-007 主失败走备用

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-007
- 依赖：`test_chat_fallback_to_ready_config`
- 步骤：主配置超时，带 fallback
- 预期结果：200，实际 config 为备用
- 清理：无
- 实际结果：使用 deepseek-r1
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-008 省略 config

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-008
- 依赖：`test_chat_requires_config`
- 步骤：只传 messages
- 预期结果：422，不调用上游
- 清理：无
- 实际结果：422
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-009 请求覆盖密钥被拒

- 优先级：P0
- 关联需求/验收标准：REQ-003 / AC-009
- 依赖：`test_chat_rejects_extra_override_fields`
- 步骤：请求带 apikey/baseurl
- 预期结果：422
- 清理：无
- 实际结果：422
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-010 对话成功

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-010
- 依赖：`test_chat_success`
- 步骤：POST `/chat` 使用就绪 chat 配置
- 预期结果：200，含 config 与非空 content
- 清理：无
- 实际结果：成功
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-011 api 不匹配

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-011
- 依赖：`test_chat_api_mismatch`
- 步骤：图像配置打 `/chat`
- 预期结果：422 `api_mismatch`
- 清理：无
- 实际结果：422
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-012 生图成功

- 优先级：P0
- 关联需求/验收标准：REQ-004 / AC-012
- 依赖：`test_generate_image_success`
- 步骤：POST generate
- 预期结果：200，含图像占位
- 清理：无
- 实际结果：成功
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-013 不注入系统提示

- 优先级：P0
- 关联需求/验收标准：REQ-005 / AC-013
- 依赖：`test_chat_does_not_inject_system_prompt`
- 步骤：仅 user 消息对话
- 预期结果：假上游首条为 HumanMessage
- 清理：无
- 实际结果：未注入 system
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-014 GET 无明文密钥

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-014
- 依赖：`test_list_configs_ready_without_secrets`、`test_crud_create_get_update_delete`
- 步骤：GET 列表与详情
- 预期结果：无 apikey 字段和明文
- 清理：无
- 实际结果：脱敏
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-015 示例 YAML 空密钥

- 优先级：P0
- 关联需求/验收标准：REQ-006 / AC-015
- 依赖：`test_env_example_points_to_yaml`
- 步骤：检查 `config/llm.yaml`
- 预期结果：无 `sk-` 实值
- 清理：无
- 实际结果：空 apikey
- 结果：通过
- 证据/缺陷：`uv run pytest` 通过

### TC-016 真实上游联调

- 优先级：P0
- 关联需求/验收标准：真实密钥路径
- 测试层级：集成
- 前置条件：本地 YAML 填入真实密钥
- 步骤：手工调用 chat 与生图
- 预期结果：非空业务结果
- 清理：不把密钥写入仓库
- 实际结果：未执行
- 结果：未执行
- 证据/缺陷：环境限制

## 5. 专项检查

- [x] 参数缺失、资源不存在。
- [x] 本需求不涉及认证。
- [x] 外部调用失败转移由假上游覆盖。
- [x] 不涉及 SQL。
- [x] 日志与响应不泄露密钥。

## 6. 验收覆盖矩阵

| 验收标准 | 测试用例 | 结果 | 说明 |
| --- | --- | --- | --- |
| AC-001 | TC-001 | 通过 | pytest |
| AC-002 | TC-002 | 通过 | pytest |
| AC-003 | TC-003 | 通过 | pytest |
| AC-004 | TC-004 | 通过 | pytest |
| AC-005 | TC-005 | 通过 | pytest |
| AC-006 | TC-006 | 通过 | pytest |
| AC-007 | TC-007 | 通过 | pytest |
| AC-008 | TC-008 | 通过 | pytest |
| AC-009 | TC-009 | 通过 | pytest |
| AC-010 | TC-010 | 通过 | pytest |
| AC-011 | TC-011 | 通过 | pytest |
| AC-012 | TC-012 | 通过 | pytest |
| AC-013 | TC-013 | 通过 | pytest |
| AC-014 | TC-014 | 通过 | pytest |
| AC-015 | TC-015 | 通过 | 静态检查 |
| 真实上游 | TC-016 | 未执行 | 需密钥 |

## 7. 缺陷与汇总

| 指标 | 数量 |
| --- | ---: |
| 用例总数 | 16 |
| 通过 | 15 |
| 失败 | 0 |
| 阻塞 | 0 |
| 不适用 | 0 |
| 未执行 | 1 |

- 测试结论：有条件通过
- 未完成项：TC-016 真实上游
- 数据清理结果：临时 YAML 与依赖覆盖已复位

> 当前全量 `uv run pytest` 53 passed，不能替代真实上游验收。

## 8. 变更记录

| 日期 | 版本 | 变更内容 | 修改人 |
| --- | --- | --- | --- |
| 2026-09-11 | 0.1 | 初稿并记录隔离 pytest 结果 | 待指定 |
