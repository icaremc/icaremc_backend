# Admin growth clinical advice APIs

No database migration — uses existing `growth_clinical_advice` tables.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/clinical-advice` | All rules with nested `growth_clinical_advice_translations` |
| GET | `/api/v1/admin/clinical-advice/{id}` | One rule + translations |
| POST | `/api/v1/admin/clinical-advice` | Create (+ optional translations) |
| PATCH | `/api/v1/admin/clinical-advice/{id}` | Patch fields / upsert translations |
| DELETE | `/api/v1/admin/clinical-advice/{id}` | Cascade-deletes translations |
| POST | `/api/v1/admin/clinical-advice/{id}/translations` | Upsert one locale |

Public `GET /api/v1/cms/clinical-advice` is unchanged for the mother app.
