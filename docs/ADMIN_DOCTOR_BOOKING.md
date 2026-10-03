# Admin doctor booking / services write API

Added for the admin portal staging bridge.

| Method | Path | Notes |
|--------|------|--------|
| PATCH | `/api/v1/admin/doctors/{doctor_id}/booking` | Body `{ currency?, services?: [{ id?, name, description?, price, is_active? }] }` — upserts services and deletes ones omitted |

Doctor-app `/api/v1/doctor/services*` remains doctor-scoped and unchanged.

