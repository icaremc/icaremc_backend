# Admin pregnancy / child CMS write APIs

Added for the admin portal staging bridge.

## Pregnancy weeks

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/pregnancy-weeks` | All weeks with nested `pregnancy_week_translations` |
| PATCH | `/api/v1/admin/pregnancy-weeks/{id}` | Patch week fields |
| DELETE | `/api/v1/admin/pregnancy-weeks/{id}` | Cascade-deletes translations |
| POST | `/api/v1/admin/pregnancy-weeks/{id}/translations` | Upsert one locale (create or update) |

Existing `POST /pregnancy-weeks` unchanged; create/patch responses also include translations.

## Child growth periods

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/child-growth-periods/{id}` | Period + translations |
| POST | `/api/v1/admin/child-growth-periods` | Create; optional `translations` |
| PATCH | `/api/v1/admin/child-growth-periods/{id}` | Patch fields and/or upsert translations |
| DELETE | `/api/v1/admin/child-growth-periods/{id}` | Cascade-deletes translations |
| POST | `/api/v1/admin/child-growth-periods/{id}/translations` | Upsert one locale |

## Follow-up visit templates

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/admin/followup-templates` | Create template |
| PATCH | `/api/v1/admin/followup-templates/{id}` | Patch (code immutable) |
| DELETE | `/api/v1/admin/followup-templates/{id}` | Delete template |

Also: admin `GET /child-growth-periods` now always nests `child_growth_period_translations` (removed a shadowed list stub).
