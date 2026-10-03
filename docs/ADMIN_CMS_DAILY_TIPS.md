# Admin daily tip CMS write APIs

Added for the admin portal staging bridge. Public `GET /api/v1/cms/daily-tips` stays read-only for the mother app.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/daily-tips` | All tips with `daily_tip_translations` |
| GET | `/api/v1/admin/daily-tips/{id}` | Single tip + translations |
| POST | `/api/v1/admin/daily-tips` | Create; optional `translations` |
| PATCH | `/api/v1/admin/daily-tips/{id}` | Patch fields and/or upsert translations |
| DELETE | `/api/v1/admin/daily-tips/{id}` | Cascade-deletes translations |
| POST | `/api/v1/admin/daily-tips/{id}/translations` | Upsert one locale |
