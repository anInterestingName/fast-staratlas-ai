# fast-staratlas-ai

FastAPI 项目骨架，基于官方 [`fastapi-new`](https://github.com/fastapi/fastapi-new) 脚手架生成，并按官方 [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) 约定拆成可扩展的目录结构。

## Quick Start

```bash
uv sync --group dev
uv run fastapi dev
```

本地 PostgreSQL 可用 Compose 启动（账号仅为本地示例）：

```bash
docker compose up -d postgres
```

访问：

- 服务首页：http://localhost:8000
- 交互文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- 就绪检查：http://localhost:8000/ready
- LLM 配置列表：http://localhost:8000/api/v1/llm/configs

部署到 FastAPI Cloud：

```bash
uv run fastapi deploy
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | 欢迎信息 |
| `GET` | `/health` | 进程活性，不探测数据库 |
| `GET` | `/ready` | 数据库就绪；不可达时返回 503 |
| `GET` | `/api/v1/llm/configs` | 列出模型配置（不含密钥） |
| `POST` | `/api/v1/llm/configs` | 创建完整配置项 |
| `PUT` | `/api/v1/llm/configs/{name}` | 更新配置项 |
| `DELETE` | `/api/v1/llm/configs/{name}` | 删除配置项 |
| `POST` | `/api/v1/llm/chat` | 对话，请求传 `config` 与可选 `fallback` |
| `POST` | `/api/v1/llm/chat/stream` | SSE 流式对话 |
| `POST` | `/api/v1/llm/images/generate` | 图像生成 |
| `POST` | `/api/v1/llm/images/edit` | 图像编辑 |

LLM 配置写在 `LLM_CONFIG` 指向的 YAML 中，每条自带 `baseurl` 和 `apikey`。示例文件密钥为空时服务仍可启动，`/` 和 `/health` 不受影响。调用方只传配置名和业务内容，不能覆盖地址或密钥。JSON 失败统一为 HTTP 状态码 + `{"detail":{"code","message"}}`；成功体、探针和 SSE 事件协议不变。

当前已接入 PostgreSQL 连接层，本迭代不创建业务表。连接串通过 `DATABASE_URL` 配置，不要把真实凭据写入仓库。

## Project Structure

```text
app/
  main.py              # FastAPI 应用入口
  core/                # 配置、异常处理与日志
  db/                  # PostgreSQL 引擎与 Session
  api/router.py        # 路由汇总
  api/routes/          # 业务路由
  schemas/             # Pydantic 模型
  llm/                 # LLM 配置、工厂与编排
tests/                 # pytest
```

- `pyproject.toml` — 依赖与工具配置
- `.env.example` — 环境变量示例
- `compose.yaml` — 本地 PostgreSQL 示例

## Lint, Format and Tests

```bash
uv run ruff check
uv run ruff format --check
uv run ruff format
uv run pytest
```

本仓库以 Ruff 作为唯一 Python lint/格式化工具。默认 pytest 不连接真实 PostgreSQL，就绪探针通过依赖覆盖验证。

日志级别通过 `LOG_LEVEL` 配置，默认 `INFO`。`HTTP_LOG` 控制是否打印 HTTP 入参和响应，默认关闭；开发联调可设为 `true`，生产请保持 `false`。打开时仍会遮蔽密钥、Token、Authorization 和连接串；`/health`、`/ready` 即使打开也不打印正文，SSE 不逐条记录 `delta`。

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [FastAPI Cloud](https://fastapicloud.com)
