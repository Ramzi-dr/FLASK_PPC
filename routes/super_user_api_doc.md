# Super User API Documentation

## 🔐 PUT /super_user/reset_password

Hard reset any user’s password by providing the **super password** (stored hashed in the env collection) and required details. This action is irreversible and must be confirmed with `force: true`.

### ✅ Requirements

- JWT Access Token (Bearer)
- JSON body with:
  - `super_password` (string, plain text)
  - `email` (string, valid user email to reset)
  - `new_password` (string, must meet complexity rules)
  - `force` (boolean, must be `true` to execute reset)

### ❌ Rejections

- Body empty or invalid
- Missing or empty fields
- Invalid email format
- User not found
- Super password incorrect
- `force` not set to true
- New password fails complexity validation (at least 8 characters, 1 uppercase, 1 digit)

### 🧪 Example JSON Request

```json
{
  "super_password": "SuperSecretPlainText",
  "email": "user@example.com",
  "new_password": "NewPass123",
  "force": true
}
```

### 🔐 Example Curl

```bash
curl -k -X PUT https://your-url/super_user/reset_password \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
        "super_password": "SuperSecretPlainText",
        "email": "user@example.com",
        "new_password": "NewPass123",
        "force": true
      }'
```

### ✅ Success Response

```json
{
  "msg": "✅ Password for user USER@EXAMPLE.COM reset successfully"
}
```
