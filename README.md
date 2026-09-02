# iCare MC FastAPI Backend

Mother, doctor, and admin APIs replacing Supabase PostgREST/Auth.

## Quick start

```bash
cp .env.example .env
docker compose up -d db
uv sync
alembic -c app/persistence/sqlalchemy/alembic.ini upgrade head
fastapi dev
# or: uvicorn app.main:app --reload
# or: python main.py
```

Skills (agent): `.agents/skills/{fastapi,fastapi-python,drizzle-patterns}` — FastAPI/Annotated deps; drizzle patterns mapped to SQLAlchemy only (no Drizzle).

Health: `GET /api/v1/health`

Bootstrap first admin: `POST /api/v1/admin/bootstrap-super-admin`

## Tests

Needs Postgres DB `app_db_test` (same credentials as `.env`):

```bash
PGPASSWORD=password psql -h localhost -U app_user -d postgres -c "CREATE DATABASE app_db_test OWNER app_user;"
uv sync --group dev
pytest
```

## Remotes

- `origin` → `icaremc/icaremc_backend` (org; push needs write access)
- `kena741` → `kena741/icaremc_backend` (working mirror)

## Jobs

```bash
python -m app.jobs.reminders
```

## Client cutover / data migration

See [docs/CUTOVER.md](docs/CUTOVER.md).
