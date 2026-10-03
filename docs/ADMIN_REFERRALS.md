# Admin referrals API

Added for the admin portal staging bridge.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/referrals` | List doctor↔patient referral links with names + `is_subscribed` |
| GET | `/api/v1/admin/referral-commissions` | List commission rows with names |
| GET/PUT | `/api/v1/admin/settings/referral` | Existing generic settings route; store `{ "commissionPercent": number }` |

Doctor-app `GET /api/v1/doctor/referrals` remains doctor-scoped and unchanged.
