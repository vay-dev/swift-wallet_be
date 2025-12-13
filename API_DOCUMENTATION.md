# Swift Wallet API Documentation

## Base URL
```
http://localhost:8000/api
```

## Authentication
All endpoints (except signup, login, and OTP requests) require JWT authentication.

**Header Format:**
```
Authorization: Bearer <access_token>
```

---

## 📱 Authentication API

### 1. Request Signup OTP
**Endpoint:** `POST /auth/signup/request-otp/`

**Request:**
```json
{
  "phone_number": "+1234567890"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "OTP sent successfully",
  "data": {
    "phone_number": "+1234567890",
    "otp_code": "1234",
    "expires_in": "5 minutes"
  }
}
```

### 2. Verify OTP & Complete Signup
**Endpoint:** `POST /auth/signup/verify-otp/`

**Request:**
```json
{
  "phone_number": "+1234567890",
  "otp_code": "1234",
  "password": "123456",
  "full_name": "John Doe",
  "email": "john@example.com",
  "device_id": "browser_fingerprint_xyz123",
  "device_name": "Chrome on Windows"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Account created successfully",
  "data": {
    "user": {
      "id": 1,
      "phone_number": "+1234567890",
      "account_number": "1234567890",
      "full_name": "John Doe",
      "is_verified": false
    },
    "tokens": {
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }
  }
}
```

### 3. Login
**Endpoint:** `POST /auth/login/`

**Request:**
```json
{
  "phone_number": "+1234567890",
  "password": "123456",
  "device_id": "browser_fingerprint_xyz123",
  "device_name": "Chrome on Windows"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Login successful",
  "data": {
    "user": {...},
    "tokens": {
      "refresh": "...",
      "access": "..."
    }
  }
}
```

**Response (Device Mismatch):**
```json
{
  "status": "error",
  "message": "Device mismatch detected",
  "error_code": "DEVICE_MISMATCH",
  "data": {
    "requires_device_change": true,
    "message": "This account is registered on a different device..."
  }
}
```

### 4. Refresh Token
**Endpoint:** `POST /auth/refresh/`

**Request:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

## 💰 Wallet API

### 5. Get Wallet Balance
**Endpoint:** `GET /wallet/wallet/balance/`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "status": "success",
  "message": "Wallet balance retrieved",
  "data": {
    "id": 1,
    "user_phone": "+1234567890",
    "user_name": "John Doe",
    "account_number": "1234567890",
    "balance": "1000.00",
    "currency": "USD",
    "is_active": true,
    "is_frozen": false
  }
}
```

### 6. Send Money
**Endpoint:** `POST /wallet/transactions/send/`

**Request:**
```json
{
  "recipient_phone": "+0987654321",
  "amount": "50.00",
  "narration": "Payment for lunch",
  "transaction_pin": "1234"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Money sent successfully",
  "data": {
    "transaction": {
      "reference": "TXN-20241126120000-ABC123",
      "amount": "50.00",
      "recipient_phone": "+0987654321",
      "status": "completed"
    },
    "new_balance": "950.00"
  }
}
```

### 7. Add Money
**Endpoint:** `POST /wallet/transactions/add-money/`

**Request:**
```json
{
  "amount": "100.00",
  "payment_method": "card",
  "description": "Adding funds"
}
```

**Payment Methods:** `card`, `bank_transfer`, `bonus`

### 8. Bill Payment
**Endpoint:** `POST /wallet/transactions/bill-payment/`

**Request:**
```json
{
  "bill_type": "airtime",
  "amount": "10.00",
  "phone_number": "+1234567890",
  "transaction_pin": "1234"
}
```

**Bill Types:** `airtime`, `data`, `electricity`, `cable_tv`

### 9. Transaction History
**Endpoint:** `GET /wallet/transactions/history/`

**Query Parameters:**
- `type`: `credit` or `debit`
- `status`: `pending`, `completed`, `failed`
- `start_date`: `2024-01-01`
- `end_date`: `2024-12-31`
- `page`: `1`
- `page_size`: `20`

**Response:**
```json
{
  "count": 50,
  "next": "http://localhost:8000/api/wallet/transactions/history/?page=2",
  "previous": null,
  "results": [
    {
      "reference": "TXN-20241126120000-ABC123",
      "transaction_type": "debit",
      "amount": "50.00",
      "recipient_phone": "+0987654321",
      "status": "completed",
      "created_at": "2024-11-26T12:00:00Z"
    }
  ]
}
```

### 10. Transaction Details
**Endpoint:** `GET /wallet/transactions/<reference>/`

---

## 🔐 Security API

### 11. Set Transaction PIN
**Endpoint:** `POST /wallet/security/pin/set/`

**Request:**
```json
{
  "pin": "1234",
  "confirm_pin": "1234"
}
```

---

## 👥 Beneficiaries API

### 12. List Beneficiaries
**Endpoint:** `GET /wallet/beneficiaries/`

**Query Parameters:**
- `favorites=true` - Filter favorites only

### 13. Add Beneficiary
**Endpoint:** `POST /wallet/beneficiaries/add/`

**Request:**
```json
{
  "phone_number": "+0987654321",
  "nickname": "Mom"
}
```

---

## 📊 Analytics API

### 14. Get Analytics
**Endpoint:** `GET /wallet/analytics/?days=7`

**Response:**
```json
{
  "status": "success",
  "data": {
    "period": "Last 7 days",
    "daily_data": [...],
    "summary": {
      "total_credits": "500.00",
      "total_debits": "300.00",
      "total_transactions": 15,
      "current_balance": "1200.00"
    }
  }
}
```

---

## 💬 AI Customer Service API

### 15. Chat with AI
**Endpoint:** `POST /wallet/support/chat/`

**Request:**
```json
{
  "message": "How do I send money?",
  "session_id": "CS-20241126-ABC12345"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "session_id": "CS-20241126-ABC12345",
    "message": "To send money: 1) Go to Send Money, 2) Enter recipient's phone...",
    "status": "active"
  }
}
```

### 16. Chat History
**Endpoint:** `GET /wallet/support/history/`

---

## 📱 Dashboard API

### 17. Get Dashboard Summary
**Endpoint:** `GET /wallet/dashboard/`

**Response:**
```json
{
  "status": "success",
  "data": {
    "wallet": {...},
    "recent_transactions": [...],
    "today_summary": {
      "total_sent": "100.00",
      "total_received": "50.00",
      "transaction_count": 3
    },
    "user_info": {
      "full_name": "John Doe",
      "phone_number": "+1234567890",
      "account_number": "1234567890",
      "is_verified": true
    }
  }
}
```

---

## 🖼️ Face Verification API

### 18. Upload Face for Verification
**Endpoint:** `POST /verification/face/upload/`

**Content-Type:** `multipart/form-data`

**Request:**
```
verification_image: <file>
```

**Response:**
```json
{
  "status": "success",
  "message": "Face verification processed",
  "data": {
    "verification_status": "approved",
    "face_detected": true,
    "clarity_score": 85.4,
    "lighting_score": 72.3,
    "message": "Face verification successful!"
  }
}
```

### 19. Check Verification Status
**Endpoint:** `GET /verification/face/status/`

---

## 👤 User Profile API

### 20. Get/Update Profile
**Endpoint:** `GET/PUT /user/profile/`

**Update Request:**
```json
{
  "full_name": "John Updated Doe",
  "email": "newemail@example.com",
  "profile": {
    "bio": "Software developer",
    "city": "New York",
    "country": "USA"
  }
}
```

### 21. Upload Profile Picture
**Endpoint:** `POST /user/profile/picture/`

---

## Error Responses

All errors follow this format:
```json
{
  "status": "error",
  "message": "Error description",
  "errors": {
    "field_name": ["Error detail"]
  }
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (device mismatch, etc.)
- `404` - Not Found
- `500` - Server Error

---

## Testing with cURL

**Example: Login**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890",
    "password": "123456",
    "device_id": "test_device_123"
  }'
```

**Example: Get Balance**
```bash
curl -X GET http://localhost:8000/api/wallet/wallet/balance/ \
  -H "Authorization: Bearer <your_access_token>"
```

---

## Notes

1. **Demo Mode:** This is a simulation. No real money is involved.
2. **OTP:** In demo mode, OTP is returned in the response for testing.
3. **Devices:** Browser fingerprinting should be implemented in the frontend.
4. **AI Chat:** Uses OpenAI GPT-4 if API key is configured, otherwise uses mock responses.
5. **Transaction PIN:** Optional but recommended for security.
6. **Phone Format:** Use international format (+1234567890)
7. **Password:** Must be exactly 6 digits

---

## Environment Variables

Required in `.env`:
```env
OPENAI_API_KEY=your_openai_key
PAYSTACK_SECRET_KEY=your_paystack_secret
PAYSTACK_PUBLIC_KEY=your_paystack_public
```
