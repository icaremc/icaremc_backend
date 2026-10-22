# iCare MC - Withdrawal & Payouts API Documentation

This document describes all endpoints related to **Bank Codes**, **Payout Methods**, **Withdrawals**, **Admin Approvals**, and **Chapa Transfer Automation**.

---

## 1. Chapa Bank Codes & Transfer Approval

### 1.1 List Supported Banks
Fetches all supported Ethiopian banks, digital wallets, and bank codes directly from Chapa.

- **Method:** `GET`
- **Path:** `/api/v1/payments/chapa/banks` *(Alias: `/api/v1/payments/banks`)*
- **Auth:** Public / Optional
- **Response (200 OK):**
```json
{
  "message": "Banks retrieved",
  "status": "success",
  "data": [
    {
      "id": "cbe",
      "name": "Commercial Bank of Ethiopia",
      "code": "cbe",
      "bank_code": "cbe",
      "swift": "CBETETAA",
      "acct_length": 13,
      "is_active": true
    },
    {
      "id": "telebirr",
      "name": "Telebirr",
      "code": "telebirr",
      "bank_code": "telebirr",
      "swift": null,
      "acct_length": 10,
      "is_active": true
    }
  ]
}
```

---

### 1.2 Chapa Transfer Approval Webhook
Chapa calls this webhook to automatically authorize and release outbound transfers.

- **Method:** `POST` / `GET`
- **Path:** `/api/v1/payments/chapa/transfer-approval` *(Alias: `/api/v1/payments/transfer-approval`)*
- **Headers:**
  - `Content-Type: application/json`
  - `chapa-signature: <HMAC-SHA256 signature or secret>`
- **Request Body (from Chapa):**
```json
{
  "amount": "500.00",
  "currency": "ETB",
  "reference": "pat-payout-211175af12bc-026d91",
  "bank": "cbe",
  "account_name": "Abebe Bikila",
  "account_number": "1000123456789"
}
```
- **Response (200 OK):**
```json
{
  "status": "approved",
  "message": "Transfer approved"
}
```

---

## 2. Patient / Mother Wallet & Withdrawals

### 2.1 Get Patient Wallet & Transactions
- **Method:** `GET`
- **Path:** `/api/v1/wallet`
- **Auth:** Bearer Token (`role: patient`)
- **Response (200 OK):**
```json
{
  "wallet": {
    "patient_id": "760341e1-8420-4b1b-bd08-68aaef511480",
    "balance": "450.00",
    "currency": "ETB"
  },
  "transactions": [
    {
      "id": "uuid",
      "amount": "100.00",
      "is_credit": false,
      "type": "withdrawal_hold",
      "note": "Withdrawal request of 100 ETB",
      "created_at": "2026-10-19T11:16:01.917Z"
    }
  ]
}
```

---

### 2.2 List Patient Payout Methods
- **Method:** `GET`
- **Path:** `/api/v1/wallet/payout-methods`
- **Auth:** Bearer Token (`role: patient`)
- **Response (200 OK):**
```json
[
  {
    "id": "a5c88a25-cd7e-47f7-af92-036444508cd8",
    "patient_id": "760341e1-8420-4b1b-bd08-68aaef511480",
    "holder_name": "Daniel Yilma",
    "account_number": "1000653707348",
    "bank_name": "Commercial Bank of Ethiopia",
    "bank_code": "cbe",
    "is_default": true,
    "currency": "ETB"
  }
]
```

---

### 2.3 Create Patient Payout Method
- **Method:** `POST`
- **Path:** `/api/v1/wallet/payout-methods`
- **Auth:** Bearer Token (`role: patient`)
- **Request Body:**
```json
{
  "holder_name": "Daniel Yilma",
  "account_number": "1000653707348",
  "bank_name": "Commercial Bank of Ethiopia",
  "bank_code": "cbe",
  "is_default": true,
  "currency": "ETB"
}
```
- **Response (200 OK):** Returns the created payout method object.

---

### 2.4 Update Patient Payout Method
- **Method:** `PATCH`
- **Path:** `/api/v1/wallet/payout-methods/{method_id}`
- **Auth:** Bearer Token (`role: patient`)
- **Request Body (all fields optional):**
```json
{
  "holder_name": "Daniel Yilma Updated",
  "account_number": "1000653707348",
  "bank_name": "CBE",
  "bank_code": "cbe",
  "is_default": true
}
```
- **Response (200 OK):** Returns the updated payout method object.

---

### 2.5 Delete Patient Payout Method
- **Method:** `DELETE`
- **Path:** `/api/v1/wallet/payout-methods/{method_id}`
- **Auth:** Bearer Token (`role: patient`)
- **Response (200 OK):** Returns `{ "ok": true }`

---

### 2.6 Request a Patient Withdrawal
Submits a withdrawal request. Immediately places funds on hold in the patient's wallet.

- **Method:** `POST`
- **Path:** `/api/v1/wallet/withdraw`
- **Auth:** Bearer Token (`role: patient`)
- **Request Body:**
```json
{
  "amount": "100.00",
  "payout_method_id": "a5c88a25-cd7e-47f7-af92-036444508cd8",
  "note": "School supplies payout"
}
```
*(If `payout_method_id` is omitted, the patient's default payout method is used).*
- **Response (200 OK):**
```json
{
  "id": "211175af-12bc-47d7-a07f-87ee0b42ccf4",
  "patient_id": "760341e1-8420-4b1b-bd08-68aaef511480",
  "amount": "100.00",
  "status": "pending",
  "note": "School supplies payout",
  "created_at": "2026-10-19T11:16:01.917Z"
}
```

---

### 2.7 List Patient Withdrawal Requests
- **Method:** `GET`
- **Path:** `/api/v1/wallet/withdrawals`
- **Auth:** Bearer Token (`role: patient`)
- **Response (200 OK):** Returns list of withdrawal requests with their current status (`pending`, `completed`, `rejected`).

---

## 3. Doctor Practice Wallet & Payouts

### 3.1 Get Doctor Wallet
- **Method:** `GET`
- **Path:** `/api/v1/doctor/wallet`
- **Auth:** Bearer Token (`role: doctor`)
- **Response (200 OK):**
```json
{
  "wallet": {
    "doctor_id": "uuid",
    "available_balance": "12000.00",
    "pending_balance": "1500.00",
    "currency": "ETB"
  },
  "transactions": []
}
```

---

### 3.2 List Doctor Payout Methods
- **Method:** `GET`
- **Path:** `/api/v1/doctor/payout-methods`
- **Auth:** Bearer Token (`role: doctor`)
- **Response (200 OK):** Returns array of doctor's saved payout methods.

---

### 3.3 Create Doctor Payout Method
- **Method:** `POST`
- **Path:** `/api/v1/doctor/payout-methods`
- **Auth:** Bearer Token (`role: doctor`)
- **Request Body:**
```json
{
  "holder_name": "Dr. Smith",
  "account_number": "1000123456",
  "bank_name": "Commercial Bank of Ethiopia",
  "bank_code": "cbe",
  "is_default": true
}
```
- **Response (200 OK):** Returns the created payout method.

---

### 3.4 Update Doctor Payout Method
- **Method:** `PATCH`
- **Path:** `/api/v1/doctor/payout-methods/{method_id}`
- **Auth:** Bearer Token (`role: doctor`)
- **Request Body:**
```json
{
  "holder_name": "Dr. John Smith",
  "is_default": true
}
```
- **Response (200 OK):** Returns the updated payout method.

---

### 3.5 Delete Doctor Payout Method
- **Method:** `DELETE`
- **Path:** `/api/v1/doctor/payout-methods/{method_id}`
- **Auth:** Bearer Token (`role: doctor`)
- **Response (200 OK):** Returns `{ "ok": true }`

---

### 3.6 Request a Doctor Payout
Moves funds from `available_balance` to `pending_balance` awaiting admin approval.

- **Method:** `POST`
- **Path:** `/api/v1/doctor/payouts`
- **Auth:** Bearer Token (`role: doctor`)
- **Request Body:**
```json
{
  "amount": "5000.00",
  "payout_method_id": "uuid"
}
```
- **Response (200 OK):** Returns created `DoctorPayoutRequest` object with `status: "pending"`.

---

### 3.7 List Doctor Payouts
- **Method:** `GET`
- **Path:** `/api/v1/doctor/payouts`
- **Auth:** Bearer Token (`role: doctor`)
- **Response (200 OK):** Returns list of doctor's past payout requests.

---

## 4. Admin Review & Action (Automatic Chapa Transfers)

### 4.1 List Patient Withdrawal Requests
- **Method:** `GET`
- **Path:** `/api/v1/admin/patient-withdrawals`
- **Auth:** Bearer Token (`role: admin`)
- **Query Parameters (all optional):**
  - `status`: Filter by status (`pending`, `approved`, `completed`, `rejected`, `processing`)
  - `patient_id` / `user_id`: Filter by patient/user UUID
  - `payout_method_id`: Filter by payout method UUID
  - `search`: Search patient full name, phone number, note, admin note, or Chapa reference
  - `min_amount`: Filter minimum withdrawal amount (e.g. `100.00`)
  - `max_amount`: Filter maximum withdrawal amount (e.g. `5000.00`)
  - `created_from` / `date_from`: Filter created at timestamp `>= created_from`
  - `created_to` / `date_to`: Filter created at timestamp `<= created_to`
  - `limit`: Number of records to return (default: `100`, max: `500`)
  - `offset`: Number of records to skip (default: `0`)
  - `page`: Page number (1-based, alternative to `offset`)
  - `page_size`: Page size (alternative to `limit`)
  - `envelope`: If `true`, returns `{ "withdrawals": [...], "total": 42, "limit": 100, "offset": 0, "page": 1 }`
- **Response Headers:**
  - `X-Total-Count`: Total number of matching records in the system
  - `X-Limit`: Applied limit
  - `X-Offset`: Applied offset
- **Response (200 OK):**
```json
[
  {
    "id": "211175af-12bc-47d7-a07f-87ee0b42ccf4",
    "patient_id": "760341e1-8420-4b1b-bd08-68aaef511480",
    "payout_method_id": "a5c88a25-cd7e-47f7-af92-036444508cd8",
    "amount": "100.00",
    "status": "pending",
    "note": "School supplies payout",
    "admin_note": null,
    "payment_date": null,
    "chapa_transfer_reference": null,
    "patient_name": "Abebech Gobena",
    "patient_phone": "0911000000",
    "patient": {
      "id": "760341e1-8420-4b1b-bd08-68aaef511480",
      "full_name": "Abebech Gobena",
      "phone": "0911000000"
    },
    "payout_method": {
      "id": "a5c88a25-cd7e-47f7-af92-036444508cd8",
      "holder_name": "Abebech Gobena",
      "account_number": "1000653707348",
      "bank_name": "Commercial Bank of Ethiopia",
      "bank_code": "cbe",
      "currency": "ETB"
    },
    "created_at": "2026-10-19T11:16:01.917Z",
    "updated_at": "2026-10-19T11:16:01.917Z"
  }
]
```

---

### 4.2 Review Patient Withdrawal Details
- **Method:** `GET`
- **Path:** `/api/v1/admin/patient-withdrawals/{request_id}`
- **Auth:** Bearer Token (`role: admin`)
- **Response (200 OK):**
```json
{
  "request": {
    "id": "211175af-12bc-47d7-a07f-87ee0b42ccf4",
    "amount": "100.00",
    "status": "pending",
    "note": "payout"
  },
  "patient": {
    "id": "760341e1-8420-4b1b-bd08-68aaef511480",
    "full_name": "Abebech",
    "phone": "251911223344"
  },
  "wallet": {
    "balance": "450.00",
    "currency": "ETB"
  },
  "payout_method": {
    "holder_name": "Abebech Gobena",
    "account_number": "1000653707348",
    "bank_name": "Commercial Bank of Ethiopia",
    "bank_code": "cbe"
  }
}
```

---

### 4.3 Action on Patient Withdrawal (Approve / Reject)
- **Method:** `POST`
- **Path:** `/api/v1/admin/patient-withdrawals/{request_id}`
- **Auth:** Bearer Token (`role: admin`)
- **Request Body (Approve):**
```json
{
  "status": "completed",
  "admin_note": "Approved and disbursed via CBE"
}
```
*Behavior on `"approved"` / `"completed"`:*
1. Automatically executes Chapa transfer disbursement to the recipient account.
2. Saves `chapa_transfer_reference` (e.g. `pat-payout-211175af12bc-026d91`).
3. Sends an urgent push notification to the patient.

- **Request Body (Reject):**
```json
{
  "status": "rejected",
  "admin_note": "Account number is invalid"
}
```
*Behavior on `"rejected"`:*
1. Automatically refunds `amount` back to the patient's `wallet.balance`.
2. Creates a credit `withdrawal_refund` transaction.
3. Sends an urgent push notification explaining the rejection reason.

---

### 4.4 List Doctor Payout Requests
- **Method:** `GET`
- **Path:** `/api/v1/admin/payout-requests`
- **Auth:** Bearer Token (`role: admin`)
- **Response (200 OK):** Returns array of doctor payout requests.

---

### 4.5 Review Doctor Payout Request
- **Method:** `GET`
- **Path:** `/api/v1/admin/payout-requests/{request_id}`
- **Auth:** Bearer Token (`role: admin`)
- **Response (200 OK):** Returns detailed information about the request, doctor profile, wallet, and payout method.

---

### 4.6 Action on Doctor Payout (Approve / Reject)
- **Method:** `POST`
- **Path:** `/api/v1/admin/payout-requests/{request_id}`
- **Auth:** Bearer Token (`role: admin`)
- **Request Body:**
```json
{
  "status": "completed",
  "admin_note": "Sent via Chapa"
}
```
*(On `"completed"` / `"approved"`, dispatches transfer via Chapa, clears `pending_balance`, and notifies doctor).*

---

### 4.7 Fetch Payment Method by ID (Admin)
Fetches payment method details (doctor or patient) using its payment method ID or user ID.

- **Method:** `GET`
- **Path:** `/api/v1/admin/payment-methods/{id}` *(Alias: `/api/v1/admin/payout-methods/{id}`, `/api/v1/payments/payment-methods/{id}`)*
- **Auth:** Bearer Token (`role: admin`)
- **Response (200 OK):**
```json
{
  "id": "a5c88a25-cd7e-47f7-af92-036444508cd8",
  "user_id": "760341e1-8420-4b1b-bd08-68aaef511480",
  "user_type": "patient",
  "patient_id": "760341e1-8420-4b1b-bd08-68aaef511480",
  "doctor_id": null,
  "holder_name": "Abebech Gobena",
  "account_number": "1000653707348",
  "bank_name": "Commercial Bank of Ethiopia",
  "bank_code": "cbe",
  "swift_code": null,
  "is_active": true,
  "is_default": true,
  "currency": "ETB",
  "created_at": "2026-10-19T11:16:01.917Z",
  "updated_at": "2026-10-19T11:16:01.917Z"
}
```
*(If `{id}` is a user ID rather than a method ID, returns an array of all payment methods belonging to that user).*

---

### 4.8 List User / Doctor Payment Methods (Admin)
- **Method:** `GET`
- **Paths:**
  - `/api/v1/admin/users/{user_id}/payment-methods`
  - `/api/v1/admin/doctors/{doctor_id}/payment-methods`
  - `/api/v1/admin/payment-methods?user_id={user_id}`
- **Auth:** Bearer Token (`role: admin`)
- **Response (200 OK):** Returns array of payment methods for the given user/doctor.
