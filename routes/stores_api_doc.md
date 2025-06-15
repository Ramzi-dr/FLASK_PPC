# 📦 Stores API Documentation

All endpoints are protected by JWT access tokens.

Base URL: `https://116.203.203.86`

---

## 🔍 GET `/stores`

**Description:** Return all stores with users and camera details.

### ✅ Requirements:
- Access token

### 🧪 Example Curl:
```bash
curl -k -X GET https://116.203.203.86/stores \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

## ➕ POST `/stores`

**Description:** Create a new store and link users (only existing ones).

### ✅ Required Fields:
- `name`: string (unique)
- Optional: `clientID`, `address`, `users` (list of emails)

### ℹ️ Notes:
- Users not found are skipped and listed in the response.
- Only existing users will be linked to store and updated.

### 🧪 Example Curl:
```bash
curl -k -X POST https://116.203.203.86/stores \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main Branch",
    "clientID": "CLIENT123",
    "address": "ZURICH",
    "users": ["admin@x.com", "staff@y.com"]
  }'
```

---

## 🔄 PUT `/stores`

**Description:** Update store fields (`clientID`, `address`, `name`).

### ❌ Cannot modify:
- `users` list (use `/stores/users` instead)

### 🧪 Example Curl (rename + update address):
```bash
curl -k -X PUT https://116.203.203.86/stores \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OLD STORE",
    "new_name": "NEW STORE",
    "address": "BERN"
  }'
```

---

## 🔴 DELETE `/stores`

**Description:** Delete one or more stores by name.

### ⚠️ Must include:
- `force: true`
- `name`: string or list of store names

### 🧪 Example Curl:
```bash
curl -k -X DELETE https://116.203.203.86/stores \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "force": true,
    "name": ["STORE A", "STORE B"]
  }'
```

---

## ➖ DELETE `/stores/users`

**Description:** Remove users from a store and sync user data.

### 🔐 Accepts:
- `store_name`: string
- Either `user_email`: string OR `user_emails`: list of strings

### 🧪 Example Curl:
```bash
curl -k -X DELETE https://116.203.203.86/stores/users \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "STORE X",
    "user_emails": ["a@x.com", "b@y.com"]
  }'
```

---

## ➕ POST `/stores/users`

**Description:** Add users to a store and sync store into user data.

### 🔐 Accepts:
- `store_name`: string
- Either `user_email`: string OR `user_emails`: list of strings

### ℹ️ Behavior:
- Skips already assigned users
- Ignores unknown users (listed in response)

### 🧪 Example Curl:
```bash
curl -k -X POST https://116.203.203.86/stores/users \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "STORE X",
    "user_emails": ["user1@x.com", "user2@y.com"]
  }'
```