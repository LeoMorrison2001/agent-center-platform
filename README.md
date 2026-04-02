# Agent Center Platform

一个用于管理智能体服务的多 Agent 平台原型，提供：

- 智能体服务注册与管理
- 基于 RabbitMQ 的任务分发
- 任务执行日志查询
- 基于 WebSocket 的实时监控
- 独立 SDK，用于接入自定义 worker

当前仓库包含后端平台、前端管理台、SDK 和示例 worker。

## Tech Stack

- Backend: FastAPI, SQLAlchemy, RabbitMQ
- Frontend: Vue 3, Vite, Pinia, TDesign
- SDK / Workers: Python
- Database: MySQL by default, SQLite also supported
- Migration: Alembic

## Repository Layout

```text
.
├─ src/                     # 后端平台代码
│  ├─ agent_platform/       # API、WebSocket、Pydantic schema
│  └─ common/               # 数据库、MQ、公共模块
├─ frontend/                # 前端管理台
├─ sdk/                     # worker 接入 SDK
├─ workers/                 # 示例 worker
├─ migrations/              # Alembic 迁移文件
├─ main.py                  # 后端启动入口
├─ alembic.ini              # Alembic 配置
└─ .env.example             # 环境变量示例
```

## Core Concepts

### Service

平台中的一个智能体服务定义，核心字段包括：

- `agent_key`: 服务唯一标识
- `name`: 服务名称
- `type`: 服务类型
- `description`: 服务描述
- `working_count`: 当前活跃实例数量

### Task Status

当前仓库统一使用以下任务状态：

- `queued`
- `completed`
- `failed`

### Monitor Events

当前仓库统一使用以下实时事件：

- `task.created`
- `task.queued`
- `task.completed`
- `task.failed`
- `instance.connected`
- `instance.disconnected`

## Requirements

- Python 3.12+
- Node.js 18+（建议）
- RabbitMQ

## Environment

先复制配置文件：

```bash
cp .env.example .env
```

Windows PowerShell 可以用：

```powershell
Copy-Item .env.example .env
```

常用环境变量：

```env
# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# MySQL
DATABASE_URL=mysql+pymysql://root:tcrj%40123456@192.168.10.212:3306/agent_platform?charset=utf8mb4

# SQLite
# DATABASE_URL=sqlite:///./sunday_agents.db

# 数据库初始化模式
# auto_create: 本地开发兜底自动建表
# migrations_only: 只依赖 Alembic
DB_INIT_MODE=auto_create
```

## Backend Setup

安装 Python 依赖后启动后端：

```bash
python main.py
```

默认监听：

- API: `http://localhost:3150`
- OpenAPI Docs: `http://localhost:3150/docs`
- Platform Info: `http://localhost:3150/api/platform/info`

## Frontend Setup

进入前端目录安装依赖并启动：

```bash
cd frontend
npm install
npm run dev
```

构建命令：

```bash
npm run build
```

## Database

项目默认使用 MySQL，也支持 SQLite。

### MySQL

示例配置：

```env
DATABASE_URL=mysql+pymysql://root:tcrj%40123456@192.168.10.212:3306/agent_platform?charset=utf8mb4
```

当前仓库已经包含 `pymysql` 依赖，默认配置即可直接连接 MySQL。建议提前创建 `agent_platform` 数据库，并使用 `utf8mb4` 字符集。

### SQLite

如需切回 SQLite，可改为：

```env
DATABASE_URL=sqlite:///./sunday_agents.db
```

## Alembic Migration

迁移文件位于 [migrations](./migrations)。

常用命令：

```bash
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic revision -m "describe change"
python -m alembic current
python -m alembic heads
```

### Existing Database

如果数据库已经存在，且表结构与当前基线一致，可以先标记到基线版本：

```bash
python -m alembic stamp head
```

本仓库当前基线版本为：

```text
20260329_2300
```

### Recommended Flow

开发环境推荐：

1. 使用 `DB_INIT_MODE=auto_create`
2. 需要演进表结构时优先写 Alembic 迁移

更正式的环境推荐：

1. 设置 `DB_INIT_MODE=migrations_only`
2. 执行 `python -m alembic upgrade head`
3. 再启动应用

## Worker Integration

自定义 worker 可以基于 SDK 接入，参考：

- [sdk/client.py](./sdk/client.py)
- [workers/test_worker/agent.py](./workers/test_worker/agent.py)
- [workers/weather_agent/agent.py](./workers/weather_agent/agent.py)

最小示例思路：

```python
from sdk import AgentWorker

worker = AgentWorker(agent_key="my_worker")

@worker.on_task
def handle_task(task: str) -> str:
    return f"done: {task}"

if __name__ == "__main__":
    worker.run()
```

## Main API

常用接口：

- `GET /api/platform/info`
- `GET /api/platform/status`
- `GET /api/platform/services`
- `POST /api/platform/services`
- `POST /api/platform/dispatch`
- `GET /api/platform/logs`
- `GET /api/platform/logs/{task_id}`
- `GET /api/platform/logs/stats/summary`
- `GET /api/platform/services/{agent_key}/instances`
- `POST /api/platform/services/{agent_key}/test`
- `GET /api/platform/tools`

WebSocket 监控端点：

- `/ws/platform/monitor`

## Notes

- 当前项目已经统一了主链路字段、任务状态和实时事件命名。
- `working_count` 目前保留原字段名以兼容现有代码和数据库，但语义上表示“活跃实例数量”。
- 当前“测试服务”能力是服务级投递，不是定向到单个实例。

## Development Tips

- 修改数据库模型时，同时更新 Alembic 迁移
- 变更 API 返回结构时，同时更新前端类型定义
- 提交前建议至少运行：

```bash
python -m compileall src sdk workers
```

前端依赖安装完成后再运行：

```bash
cd frontend
npm run build
```
