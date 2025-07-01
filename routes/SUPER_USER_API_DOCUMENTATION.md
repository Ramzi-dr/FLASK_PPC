
# 🔐 Super User API Documentation

This endpoint allows privileged password resets with a verified `SUPER_PASSWORD`.

---

## 🔁 PUT `/super_user/reset_password` — Force Reset User Password

Use this route to reset any user's password by verifying the hashed super password stored in the database.

### 🔐 Headers
- `Authorization: Bearer <TOKEN>`
- `Content-Type: application/json`

### ⚠️ Restrictions
- Requires valid `SUPER_PASSWORD` (stored hashed in `env` collection)
- Requires `"force": true` in the body

### 📨 Request Body
```json
{
  "super_password": "SuperSecure123",
  "email": "user@example.com",
  "new_password": "NewPass123",
  "force": true
}
```

### ✅ Success Response
- Code: `200 OK`
```json
{
  "msg": "✅ Password for user USER@EXAMPLE.COM reset successfully"
}
```

### ❌ Error Responses
- `400 Bad Request`
  - Empty body
  - Missing or malformed `email`, `super_password`, or `new_password`
  - Password too weak (must be 8+ chars, 1 uppercase, 1 digit)
  - `"force"` not set to true
- `403 Forbidden`
  - Invalid `super_password`
- `404 Not Found`
  - User not found
- `500 Internal Server Error`
  - Missing `SUPER_PASSWORD` config or DB error

### 🧪 Example `curl`
```bash
curl -k -X PUT https://your-url/super_user/reset_password \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "super_password": "SuperSecure123",
    "email": "user@example.com",
    "new_password": "NewPass123",
    "force": true
  }'
```

---
