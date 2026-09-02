---
name: drizzle-patterns
description: Drizzle ORM best practices (schema, indexes, transactions, migrations). Adapted here for SQLAlchemy/Postgres — this backend is not Drizzle/TS.
---

# Drizzle ORM Patterns (adapted for icaremc_backend)

Upstream skill targets Drizzle + SQLite/TS. This repo uses SQLAlchemy 2 + asyncpg + Alembic.
Keep the *ideas*; do not introduce Drizzle.

## Apply as SQLAlchemy

| Drizzle guidance | Here |
|---|---|
| Index all FKs + hot WHERE cols | `index=True` / `Index(...)` on models + Alembic |
| Transactions for multi-table writes | `get_db` commit/rollback; flush order in services |
| Migration workflow | edit models → `alembic revision` → review → upgrade |
| Select only needed columns | prefer explicit `select(Model.col, ...)` on hot paths |
| Cascade deletes where owned | already on several FKs (`ondelete="CASCADE"`) |
| Prepared statements | asyncpg + SQLAlchemy compile cache covers this; skip manual prepare |

## Do not

- Add Drizzle, Turso, or SQLite
- Rewrite schema into TypeScript
- Swap UUIDs for nanoid
