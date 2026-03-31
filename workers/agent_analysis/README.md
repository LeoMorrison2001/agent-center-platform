# agent_analysis worker

## 初始化独立环境

```powershell
cd workers\agent_analysis
uv sync
```

## 配置

复制 `.env.example` 为 `.env`，至少配置：

```env
MODEL_PROVIDER=tongyi
MODEL_NAME=qwen3-max
TONGYI_API_KEY=your-real-key
RABBITMQ_URL=amqp://admin:123456@192.168.10.115:5672/%2Fagent
PLATFORM_API_BASE_URL=http://127.0.0.1:3150
```

## 启动

```powershell
cd workers\agent_analysis
uv run agent.py
```

说明：

- 该 worker 使用自己的 uv 环境。
- 运行时会复用仓库根目录下的 `sdk` 代码。
- 若平台未创建 `agent_analysis` 服务，worker 会拒绝启动。
