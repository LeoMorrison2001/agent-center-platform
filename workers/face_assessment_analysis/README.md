# face_assessment_analysis worker

## 初始化独立环境
```powershell
cd workers\face_assessment_analysis
uv sync
```

## 配置

至少配置：

```env
MODEL_PROVIDER=tongyi
MODEL_NAME=qwen3-max
TONGYI_API_KEY=your-real-key
RABBITMQ_URL=amqp://admin:tcrj%40123456@192.168.10.212:5672/%2Fagent
PLATFORM_API_BASE_URL=http://192.168.10.212:2001
```

## 启动

```powershell
cd workers\face_assessment_analysis
uv run agent.py
```

说明：
- 该 worker 使用独立 uv 环境
- 会复用仓库根目录下的 `sdk`
- 平台需先创建 `face_assessment_analysis` 服务
