
# 🏬 Store Management API Documentation

All routes below require **JWT access token**.

---

## 📥 GET `/stores` — List All Stores

Returns all stores with metadata, users, and camera info.

### ✅ Response
```json
{
  "stores": [
    {
      "name": "STORE1",
      "clientID": "CLIENT123",
      "address": "BERN",
      "users": ["USER1@EMAIL.COM"],
      "open_time": "08:00",
      "close_time": "18:00",
      "cameras": []
    }
  ]
}
```

---

## ➕ POST `/stores` — Create Store

Create a new store with optional user emails.

### 📤 Request Body
```json
{
  "name": "STORE1",
  "clientID": "CLIENT123",
  "address": "Bern",
  "users": ["user1@email.com"],
  "open_time": "08:00",
  "close_time": "18:00"
}
```

### ✅ Response
- Code: `201 Created`
```json
{
  "msg": "✅ Store created. Non-existing users ignored: USER2@EMAIL.COM...",
  "store": { ... }
}
```

### ❌ Errors
- `400`: Missing name, invalid times, or bad user format
- `409`: Store name already exists

---

## 🔄 PUT `/stores` — Update Store

Update store fields and optionally rename store.

### 📤 Request Body
```json
{
  "name": "STORE1",
  "new_name": "STORE2",
  "address": "New Address",
  "open_time": "09:00",
  "close_time": "17:00"
}
```

### ✅ Response
```json
{
  "msg": "✅ Store 'STORE1' updated",
  "store": { ... }
}
```

### ❌ Errors
- `400`: Bad fields, format, or logic
- `404`: Store not found
- `409`: New name already exists

---

## 🔴 DELETE `/stores` — Delete Store(s)

Delete one or multiple stores.

### 📤 Request Body
```json
{
  "name": ["STORE1", "STORE2"],
  "force": true
}
```

### ✅ Response
```json
{
  "msg": "✅ Deleted stores: STORE1. ❌ Not found stores: STORE2."
}
```

### ❌ Errors
- `400`: No name or `force` missing

---

## ➖ DELETE `/stores/users` — Remove Users from Store

Remove users from a store.

### 📤 Request Body
```json
{
  "store_name": "STORE1",
  "user_emails": ["USER1@EMAIL.COM"]
}
```

### ✅ Response
```json
{
  "msg": "✅ Removed users: USER1@EMAIL.COM. ❌ Users not found: MISSING@EMAIL.COM"
}
```

---

## ➕ POST `/stores/users` — Add Users to Store

Assign users to a store.

### 📤 Request Body
```json
{
  "store_name": "STORE1",
  "user_emails": ["USER1@EMAIL.COM", "MISSING@EMAIL.COM"]
}
```

### ✅ Response
```json
{
  "msg": "✅ Added users: USER1@EMAIL.COM. ❌ Users not found: MISSING@EMAIL.COM"
}
```

---

### 🧪 Curl Example
```bash
curl -X POST https://your-url/stores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Store1", "users": ["user1@email.com"], "open_time": "08:00", "close_time": "18:00" }'
```

---
