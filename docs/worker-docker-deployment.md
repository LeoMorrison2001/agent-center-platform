# Worker Docker Deployment

Workers do not need to expose any ports.
They only need outbound access to:

- RabbitMQ
- Platform API

## One container, many replicas

The worker image supports starting multiple worker processes inside one container.

Control it with:

```env
WORKER_REPLICAS=5
```

Each process will start its own worker instance and register a unique `instance_id`.

## Build and run one worker

Build `agent_analysis`:

```bash
docker build -t agent-analysis-worker:latest -f workers/Dockerfile --build-arg WORKER_DIR=agent_analysis .
```

Run 5 replicas in one container:

```bash
docker run -d \
  --name agent-analysis-worker \
  --env-file workers/agent_analysis/.env \
  -e WORKER_DIR=agent_analysis \
  -e WORKER_REPLICAS=5 \
  --restart unless-stopped \
  agent-analysis-worker:latest
```

Build `face_assessment_analysis`:

```bash
docker build -t face-assessment-analysis-worker:latest -f workers/Dockerfile --build-arg WORKER_DIR=face_assessment_analysis .
```

Run 5 replicas in one container:

```bash
docker run -d \
  --name face-assessment-analysis-worker \
  --env-file workers/face_assessment_analysis/.env \
  -e WORKER_DIR=face_assessment_analysis \
  -e WORKER_REPLICAS=5 \
  --restart unless-stopped \
  face-assessment-analysis-worker:latest
```

## Use docker compose

The repository includes:

- `docker-compose.workers.yml`

Start both worker groups:

```bash
docker compose -f docker-compose.workers.yml up -d --build
```

The default compose file starts:

- 5 `agent_analysis` replicas in one container
- 5 `face_assessment_analysis` replicas in one container

Adjust the replica count by changing:

```yaml
WORKER_REPLICAS: "5"
```
