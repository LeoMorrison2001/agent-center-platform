# Docker Deployment

This project can run the frontend and backend in a single container.
The container serves the built Vue frontend with Nginx and proxies `/api` and `/ws` to the internal FastAPI service.

Default external ports:

- `2000` for frontend
- `2001` for backend API

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
http://YOUR_SERVER_IP:2000
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
  -p 2000:80 \
  -p 2001:3150 \
  --restart unless-stopped \
  agent-center-platform:latest
```

## Internal layout

- Nginx listens on `80`
- FastAPI listens on `0.0.0.0:3150`
- WebSocket path stays `/ws/platform/monitor`

## Changing the host port

If `2000` or `2001` is occupied, only change the left side of the mapping:

```bash
docker run -p 18000:80 -p 18001:3150 ...
```

or in `docker-compose.yml`:

```yaml
ports:
  - "18000:80"
  - "18001:3150"
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
