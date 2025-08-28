# 🏬 Store Management API — Full Docs (with `production`)

All routes require a valid **JWT access token**.  
This API manages stores, their users, and metadata.

**Normalization rules (important):**
- All string inputs are normalized to **UPPERCASE** on the backend (`name`, `clientID`, `address`, `email`, etc.).
- `production` accepts **boolean** or **"true"/"false"** strings (case-insensitive). Default is **true**.
- Time fields expect **24h `HH:MM`**. On **POST**:
  - If neither is provided → `open_time="00:00"`, `close_time="23:59"`.
  - If `close_time` is provided, `open_time` is **required**.
  - If only `open_time` is provided → `close_time="23:59"`.
  - `open_time` must be **earlier** than `close_time`.
- Users list on create: non-existing users are **ignored** (returned in message).

---

## 📥 GET `/stores` — List All Stores

Returns all stores with normalized fields and cameras (camera `_id` is stringified if present).

### Response 200
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
      "production": true,
      "cameras": []
    }
  ]
}
```

### cURL
```bash
curl -X GET https://your-url/stores   -H "Authorization: Bearer <TOKEN>"
```

---

## ➕ POST `/stores` — Create Store (Admins only)

Creates a store. Validates name uniqueness, time logic, user email format, and `production`.

### Request Body
```json
{
  "name": "Store1",
  "clientID": "CLIENT123",
  "address": "Bern",
  "users": ["user1@email.com", "missing@email.com"],
  "open_time": "08:00",
  "close_time": "18:00",
  "production": false
}
```

### Response 201
```json
{
  "msg": "✅ Store created. Non-existing users ignored: MISSING@EMAIL.COM.",
  "store": {
    "name": "STORE1",
    "clientID": "CLIENT123",
    "address": "BERN",
    "users": ["USER1@EMAIL.COM"],
    "cameras": [],
    "open_time": "08:00",
    "close_time": "18:00",
    "production": false
  }
}
```

### Errors
- 400: Empty body, missing/invalid `name`, invalid time(s), invalid `production` type/value, `USERS` not a list
- 409: Store with same `name` already exists

### cURL
```bash
curl -X POST https://your-url/stores   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{
    "name":"Store1",
    "clientID":"CLIENT123",
    "address":"Bern",
    "users":["user1@email.com"],
    "open_time":"08:00",
    "close_time":"18:00",
    "production":false
  }'
```

---

## 🔄 PUT `/stores` — Update Store (Admins only)

Updates store fields. Supports optional rename via `new_name`.  
`production` accepts boolean or `"true"/"false"`.  
**Note:** PUT does not re-validate times against each other; provide valid `HH:MM`.

### Request Body (examples)
Rename + toggle production:
```json
{
  "name": "STORE1",
  "new_name": "STORE2",
  "production": true
}
```

Update time window:
```json
{
  "name": "STORE2",
  "open_time": "09:00",
  "close_time": "17:00"
}
```

Update other fields:
```json
{
  "name": "STORE2",
  "address": "ZURICH",
  "clientID": "ACME-002"
}
```

### Response 200
```json
{
  "msg": "✅ Store 'STORE1' updated",
  "store": {
    "name": "STORE2",
    "clientID": "ACME-002",
    "address": "ZURICH",
    "users": ["USER1@EMAIL.COM"],
    "cameras": [],
    "open_time": "09:00",
    "close_time": "17:00",
    "production": true
  }
}
```

### Errors
- 400: Empty body, invalid `production` type/value
- 404: Current store not found
- 409: `new_name` already exists
- 200: If no changes detected → `"ℹ️ No changes detected to update"`

### cURL
```bash
curl -X PUT https://your-url/stores   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{
    "name":"STORE1",
    "new_name":"STORE2",
    "production":true,
    "open_time":"09:00",
    "close_time":"17:00"
  }'
```

---

## 🔴 DELETE `/stores` — Delete Store(s) (Admins only)

Deletes one or multiple stores. Requires explicit confirmation.

### Request Body
```json
{
  "name": ["STORE1", "STORE2"],
  "force": true
}
```

### Response 200
```json
{
  "msg": "✅ Deleted stores: STORE1. ❌ Not found stores: STORE2."
}
```

- Also removes store references from `users.stores` and `cameras.stores`.

### Errors
- 400: Empty body, missing `name`, or `force` not `true`

### cURL
```bash
curl -X DELETE https://your-url/stores   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{ "name":["STORE1","STORE2"], "force":true }'
```

---

## ➖ DELETE `/stores/users` — Remove Users from a Store (Admins only)

Removes one or many users from a store.  
Accepts either `user_email` (string) **or** `user_emails` (array), not both.

### Request Body (single)
```json
{
  "store_name": "STORE2",
  "user_email": "user1@email.com"
}
```

### Request Body (multiple)
```json
{
  "store_name": "STORE2",
  "user_emails": ["user1@email.com", "ghost@email.com"]
}
```

### Response 200 (example)
```json
{
  "msg": "✅ Removed: USER1@EMAIL.COM. ❌ Not found: GHOST@EMAIL.COM. ❌ Not in store: MISSING@EMAIL.COM"
}
```

### Errors
- 400: Empty body, missing `store_name`, both single+list provided, bad types, empty list
- 404: Store not found

### cURL
```bash
curl -X DELETE https://your-url/stores/users   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{ "store_name":"STORE2", "user_emails":["user1@email.com"] }'
```

---

## ➕ POST `/stores/users` — Add Users to a Store (Admins only)

Adds existing users to a store; non-existing users are reported.

### Request Body (single or multiple)
```json
{
  "store_name": "STORE2",
  "user_emails": ["user1@email.com", "missing@email.com"]
}
```
> You can also use `"user_email": "..."` instead of `user_emails`.

### Response 200 (example)
```json
{
  "msg": "✅ Added: USER1@EMAIL.COM. ℹ️ Already in store: USER1@EMAIL.COM. ❌ Not found: MISSING@EMAIL.COM"
}
```

### Errors
- 400: Empty body, missing `store_name`, missing `user_email(s)`, wrong type
- 404: Store not found

### cURL
```bash
curl -X POST https://your-url/stores/users   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{ "store_name":"STORE2", "user_emails":["user1@email.com"] }'
```

---

## 👤 POST `/stores/by_user` — List Stores for a User

Returns stores where the given user (email) is assigned.  
Email is validated and normalized to uppercase.

### Request Body
```json
{
  "email": "user1@email.com"
}
```

### Response 200
```json
{
  "stores": [
    {
      "name": "STORE2",
      "clientID": "ACME-002",
      "address": "ZURICH",
      "users": ["USER1@EMAIL.COM"],
      "open_time": "09:00",
      "close_time": "17:00",
      "production": true,
      "cameras": []
    }
  ]
}
```

### Errors
- 400: Missing/invalid `email`

### cURL
```bash
curl -X POST https://your-url/stores/by_user   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{ "email":"user1@email.com" }'
```

---

## 🔒 Auth Notes

- All endpoints require `Authorization: Bearer <TOKEN>`.
- Admin-only endpoints: `POST /stores`, `PUT /stores`, `DELETE /stores`, `POST /stores/users`, `DELETE /stores/users`.

## 🧩 Field Summary

| Field         | Type                     | Notes                                                                 |
|---------------|--------------------------|-----------------------------------------------------------------------|
| name          | string (UPPER)           | Required on create; must be unique.                                   |
| new_name      | string (UPPER)           | Optional on update; must be unique.                                   |
| clientID      | string (UPPER)           | Optional.                                                             |
| address       | string (UPPER)           | Optional.                                                             |
| users         | string[] (UPPER EMAILS)  | Optional on create; invalid/missing users ignored with note.          |
| open_time     | string `HH:MM`           | See POST rules; expected valid format on PUT.                         |
| close_time    | string `HH:MM`           | See POST rules; expected valid format on PUT.                         |
| production    | boolean / "true"/"false" | Optional; default `true`.                                             |
| cameras       | array                    | Returned as-is; `_id` coerced to string if present in camera objects. |

---
