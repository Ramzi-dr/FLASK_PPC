
# 🛠️ Admin API Documentation

This admin route allows updating JWT access and refresh token expiry times.  
Access is restricted to **localhost** and **Basic Auth** credentials stored in the `env` database.

---

## 🔁 POST `/set_token_expiry` — Update Token Expiry

Set or override the duration of access and/or refresh JWT tokens.  
Must be called from `127.0.0.1` or `::1`, using HTTP Basic Auth.

### 🔐 Headers
- `Authorization: Basic <base64-encoded admin:password>`
- `Content-Type: application/json`

### 🌐 Access Control
- Only accessible from **localhost**
- Requires valid **Basic Auth**
- Requires presence of `FLASK_USER` and `FLASK_PASSWORD` in `env` collection

### 📨 Request Body
Provide one or more of the following fields:

| Field              | Type   | Description                 |
|-------------------|--------|-----------------------------|
| `access_second`   | int    | JWT access token in seconds |
| `access_minute`   | int    | JWT access token in minutes |
| `access_hour`     | int    | JWT access token in hours   |
| `access_day`      | int    | JWT access token in days    |
| `refresh_second`  | int    | JWT refresh token in seconds|
| `refresh_minute`  | int    | JWT refresh token in minutes|
| `refresh_hour`    | int    | JWT refresh token in hours  |
| `refresh_day`     | int    | JWT refresh token in days   |

Example:
```json
{
  "access_hour": 1,
  "refresh_day": 7
}
```

### ✅ Success Response
```json
{
  "msg": "✅ Token expiry updated and old tokens invalidated",
  "access_token_expires_seconds": 3600,
  "refresh_token_expires_seconds": 604800
}
```

### ❌ Error Responses
- `400 Bad Request` — No valid timing fields given
- `401 Unauthorized` — Missing or invalid basic auth
- `403 Forbidden` — Not accessed from localhost
- `500 Internal Server Error` — Missing env credentials or config error

### 🧪 Example `curl` (run from server localhost):
```bash
curl -X POST http://127.0.0.1:5000/set_token_expiry \
  -u admin:adminpassword \
  -H "Content-Type: application/json" \
  -d '{"access_hour": 2, "refresh_day": 3}'
```

---
