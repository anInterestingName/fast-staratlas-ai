# fast-staratlas-ai

FastAPI 项目骨架，基于官方 [`fastapi-new`](https://github.com/fastapi/fastapi-new) 脚手架生成，并按官方 [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) 约定拆成可扩展的目录结构。

## Quick Start

```bash
uv sync --group dev
uv run fastapi dev
```

访问：

- 服务首页：http://localhost:8000
- 交互文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- Demo 接口：http://localhost:8000/api/v1/demo

部署到 FastAPI Cloud：

```bash
uv run fastapi deploy
```

## Demo API

内存版示例接口，展示路由拆分、Pydantic 模型和基础 CRUD。

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | 欢迎信息 |
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/v1/demo` | 列出 demo 条目，支持 `q` 关键字过滤 |
| `GET` | `/api/v1/demo/{item_id}` | 按 ID 查询 |
| `POST` | `/api/v1/demo` | 创建 demo 条目 |

创建示例：

```bash
curl -X POST http://localhost:8000/api/v1/demo \
  -H "Content-Type: application/json" \
  -d '{"name": "nebula", "message": "Created by the demo API"}'
```

## Project Structure

```text
app/
  main.py              # FastAPI 应用入口
  core/config.py       # 配置
  api/router.py        # 路由汇总
  api/routes/          # 业务路由
  schemas/             # Pydantic 模型
tests/                 # pytest
```

- `pyproject.toml` — 依赖与工具配置
- `.env.example` — 环境变量示例

## Tests

```bash
uv run pytest
```

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [FastAPI Cloud](https://fastapicloud.com)
