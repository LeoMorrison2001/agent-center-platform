# Agent Center Platform

## Database

The project reads `DATABASE_URL` from `.env`.

Examples:

```env
DATABASE_URL=sqlite:///./sunday_agents.db
# DATABASE_URL=mysql+pymysql://user:password@localhost:3306/agent_platform
```

`DB_INIT_MODE` controls startup behavior:

```env
DB_INIT_MODE=auto_create
```

- `auto_create`: local-development fallback; app startup will call `create_all()`
- `migrations_only`: rely on Alembic migrations only

## Alembic

Migration files live under `migrations/`.

Common commands:

```bash
alembic upgrade head
alembic downgrade -1
alembic revision -m "describe change"
```

For an existing database that already has the current tables and should be treated as baseline:

```bash
alembic stamp head
```

Recommended production flow:

1. Set `DB_INIT_MODE=migrations_only`
2. Run `alembic upgrade head`
3. Start the application
