# Admin appointment detail and children APIs

Added for the admin portal staging bridge.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/appointments/{id}` | Returns `{ appointment, conversation: null, messages: [] }` |
| GET | `/api/v1/admin/children` | Paginated list (`limit`) |
| GET | `/api/v1/admin/children/{id}` | Single child row |


