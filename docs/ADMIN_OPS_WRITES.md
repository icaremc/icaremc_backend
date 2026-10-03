# Admin ops write APIs

Added for the admin portal staging bridge.

| Method | Path | Notes |
|--------|------|--------|
| PATCH | `/api/v1/admin/appointments/{id}` | Body `{ "status": "pending\|confirmed\|completed\|cancelled" }` |
| PATCH | `/api/v1/admin/admins/{id}` | Super-admin only; `{ is_active?, admin_role?, full_name? }` |
| POST | `/api/v1/admin/documents` | JSON metadata after upload (`title`, `category`, `storage_path`, `file_name`, `mime_type`) |
| GET | `/api/v1/admin/doctors/{id}/document-deliveries` | Delivery history for a doctor recipient |

Upload files via existing `POST /api/v1/uploads/`, then register with `POST /documents`.
