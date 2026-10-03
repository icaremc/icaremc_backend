# Admin doctor wallet API

Added for the admin portal staging bridge.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/doctors/{doctor_id}/wallet` | Returns `{ history: { wallet, commissionPercent, earnings, transactions } }` matching the admin doctor wallet panel |

Doctor-app `GET /api/v1/doctor/wallet` remains doctor-scoped and unchanged.
