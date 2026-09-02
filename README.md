# iCare MC FastAPI Backend

Mother, doctor, and admin APIs replacing Supabase PostgREST/Auth.

## Quick start

```bash
cp .env.example .env
docker compose up -d db
uv sync
alembic -c app/persistence/sqlalchemy/alembic.ini upgrade head
uvicorn main:app --reload
```

Health: `GET /api/v1/health`

Bootstrap first admin: `POST /api/v1/admin/bootstrap-super-admin`

## Remotes

- `origin` → `icaremc/icaremc_backend` (org; push needs write access)
- `kena741` → `kena741/icaremc_backend` (working mirror)

## Jobs

```bash
python -m app.jobs.reminders
```

## Client cutover / data migration

See [docs/CUTOVER.md](docs/CUTOVER.md).
