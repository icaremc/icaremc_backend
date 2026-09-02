# Client cutover & data migration

## Goal

Flutter (`mc-app`, `mc-doctor-app`) and `icaremc-admin` stop using Supabase Auth / PostgREST / RLS. They call this FastAPI (`/api/v1/...`) with Bearer JWTs.

## API map (high level)

| Client area | Old | New |
|-------------|-----|-----|
| Auth | supabase_flutter Auth + SMS | `/api/v1/auth/*` |
| Mother data | `.from('profiles'|...)` | `/api/v1/me/*`, `/pregnancies`, `/children`, … |
| Doctor ops | doctor repos | `/api/v1/doctor/*` |
| Admin | Next `app/api/admin/*` + supabase | `/api/v1/admin/*` |
| Payments | Chapa + edge/RPC | `/api/v1/payments/chapa/*` |
| Push | edge / admin routes | `/api/v1/push/notify` + FCM |
| Reminders | edge `child-followup-reminders` | `python -m app.jobs.reminders` |

## Cutover steps

1. Deploy FastAPI + Postgres; run Alembic.
2. Run `scripts/migrate_from_supabase.py` against a read-only Supabase dump / connection (passwords cannot be imported — users reset via OTP).
3. Point staging Flutter/admin `API_BASE_URL` at FastAPI; keep Supabase read-only as fallback until smoke tests pass.
4. Production flip; disable anon PostgREST keys.

## Password migration

Supabase Auth hashes are not portable to this Argon2 store. Migration creates `users` rows with a random unusable hash and sets `must_reset` via forcing password OTP on first login (clients should treat 401 + `password_reset_required` once that flag is added). Until then: broadcast reset-OTP flow.

## Schema ownership

Alembic in this repo is source of truth. Do not apply new Supabase SQL migrations after cutover.
