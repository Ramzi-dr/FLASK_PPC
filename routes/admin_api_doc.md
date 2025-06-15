# 🛡️ Admin API — Token Expiry Control (Only Localhost)

This API allows the admin to dynamically set access and refresh token expiration times **during runtime**.

---

## 🔐 Endpoint: `POST /set_token_expiry`

### 🔒 Security Requirements:
- **Basic Auth**: Username and password are securely stored bcrypt-hashed in your DB (`env` collection).
- **Local Access Only**: Allowed only from `127.0.0.1` or `::1`. Remote IPs will be rejected.
- **Admin Auth Required**: Must use correct credentials to access.

---

### ✅ Accepted JSON Payload:

You can specify token expiry using combinations of time units for access and refresh tokens:

```json
{
  "access_minute": 3,
  "refresh_hour": 2
}
```

> ⏱️ This means access tokens will expire in 3 minutes (180s) and refresh tokens in 2 hours (7200s).

---

### 🔃 Behavior:

- Converts all provided units to **seconds**.
- Updates the server config values (`JWT_ACCESS_TOKEN_EXPIRES`, `JWT_REFRESH_TOKEN_EXPIRES`).
- Immediately **invalidates all old tokens** by updating a `TOKEN_ISSUED_AFTER` timestamp.
- Stores the new expiry values in your `env` collection.

---

### ❌ Errors:

- Missing or invalid Basic Auth → `401 Unauthorized`
- Wrong password or user → `403 Forbidden`
- Remote request (not from localhost) → `403 Forbidden`
- Bad input (e.g., negative values) → `400 Bad Request`

---

### 🧪 Example `curl` from localhost:

```bash
curl -u AdminHS:Security@Home15! -X POST http://127.0.0.1:5000/admin/set_token_expiry -H "Content-Type: application/json" -d '{"access_minute":1,"refresh_day":1}'
```

---

### ✅ Example Success Response:

```json
{
  "msg": "✅ Token expiry updated and old tokens invalidated",
  "access_token_expires_seconds": 300,
  "refresh_token_expires_seconds": 86400
}
```

---

## 📌 Notes

- You can set either `access_*`, `refresh_*`, or both.
- Time fields: `*_second`, `*_minute`, `*_hour`, `*_day`
- All updates require **local** request with **valid Basic Auth**