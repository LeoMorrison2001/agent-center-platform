# Docker Deployment

This project can run the frontend and backend in a single container.
The container serves the built Vue frontend with Nginx and proxies `/api` and `/ws` to the internal FastAPI service.

Default external port:

- `8088`

This avoids host port `80`, which is often already occupied.

## What stays outside the container

- RabbitMQ
- MySQL or PostgreSQL
- Worker processes

## Required environment

Create `.env` from `.env.example` and set at least:

```env
RABBITMQ_URL=amqp://user:password@rabbitmq-host:5672/%2Fagent
DATABASE_URL=mysql+pymysql://user:password@db-host:3306/agent_platform?charset=utf8mb4
DB_INIT_MODE=migrations_only
```

If the container connects to services on the same server, use the server IP or reachable DNS name.
Do not use `127.0.0.1` unless RabbitMQ and the database are running inside the same container.

## Start with Docker Compose

```bash
docker compose up -d --build
```

Then open:

```text
http://YOUR_SERVER_IP:8088
```

## Start with plain Docker

Build:

```bash
docker build -t agent-center-platform:latest .
```

Run:

```bash
docker run -d \
  --name agent-center-platform \
  --env-file .env \
  -e RUN_MIGRATIONS=true \
  -e DB_INIT_MODE=migrations_only \
  -p 8088:8088 \
  --restart unless-stopped \
  agent-center-platform:latest
```

## Internal layout

- Nginx listens on `8088`
- FastAPI listens on `127.0.0.1:3150`
- WebSocket path stays `/ws/platform/monitor`

## Changing the host port

If `8088` is also occupied, only change the left side of the mapping:

```bash
docker run -p 18088:8088 ...
```

or in `docker-compose.yml`:

```yaml
ports:
  - "18088:8088"
```

## Database migration behavior

The startup script runs:

```bash
python -m alembic upgrade head
```

Disable this by setting:

```env
RUN_MIGRATIONS=false
```
