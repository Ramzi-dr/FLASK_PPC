
# Camera API Documentation

Base URL: `https://116.203.203.86`

---

## 🔐 Authentication

All endpoints require a valid JWT token passed in the `Authorization` header as:
```
Authorization: Bearer <JWT_TOKEN>
```

---

## 📸 Create Camera

**POST /cameras**

Creates a new camera entry. You can optionally attach it to a store.

### Required fields:
- `url` (must include protocol + port)
- `username`
- `password`

### Optional fields:
- `name`
- `store` (must already exist)

All `url`, `name`, and `store` values are uppercased. Password is stored in plain text.

#### Example with store:
```bash
curl -X POST https://116.203.203.86/cameras   -H "Authorization: Bearer <JWT_TOKEN>"   -H "Content-Type: application/json"   -d '{
        "url": "http://192.168.1.100:554",
        "username": "admin",
        "password": "pass123",
        "store": "MAIN STORE",
        "name": "Front Door Cam"
      }'
```

#### Example without store:
```bash
curl -X POST https://116.203.203.86/cameras   -H "Authorization: Bearer <JWT_TOKEN>"   -H "Content-Type: application/json"   -d '{
        "url": "http://192.168.1.100:554",
        "username": "admin",
        "password": "pass123",
        "name": "Front Door Cam"
      }'
```

---

## 🛠️ Update Camera

**PUT /cameras**

Updates a camera by URL. You can use `"url"` for current camera, or `"current_url"` + `"new_url"` to update the URL.

Allowed fields:
- `new_url` (if changing)
- `name`
- `username`
- `password`

❌ Cannot update `stores` (explicitly blocked).

### Example without changing URL:
```bash
curl -X PUT https://116.203.203.86/cameras   -H "Authorization: Bearer <JWT_TOKEN>"   -H "Content-Type: application/json"   -d '{
    "url": "http://192.168.1.100:554",
    "name": "Updated Camera Name",
    "username": "newAdminUser",
    "password": "newSecurePassword123"
  }'
```

### Example with changing URL:
```bash
curl -X PUT https://116.203.203.86/cameras   -H "Authorization: Bearer <JWT_TOKEN>"   -H "Content-Type: application/json"   -d '{
    "current_url": "http://192.168.1.100:554",
    "new_url": "http://192.168.1.100:556",
    "name": "Updated Camera Name",
    "username": "newAdminUser",
    "password": "newSecurePassword123"
  }'
```

---

## ➕ Add Store to Camera

**POST /cameras/add_store**

Adds a store to an existing camera if it’s not already linked. Also syncs camera ref in the store.

### Required fields:
- `url` (camera)
- `store` (must exist)

#### Example:
```bash
curl -X POST https://116.203.203.86/cameras/add_store   -H "Authorization: Bearer <JWT_TOKEN>"   -H "Content-Type: application/json"   -d '{
    "url": "http://192.168.1.100:554",
    "store": "MAIN STORE"
  }'
```

---

## ➖ Remove Store from Camera

**POST /cameras/remove_store**

Removes a store from a camera’s store list, and removes the camera from the store's camera list.

### Required fields:
- `url` (camera)
- `store` (must exist and be attached)

#### Example:
```bash
curl -X POST https://116.203.203.86/cameras/remove_store   -H "Authorization: Bearer <JWT_TOKEN>"   -H "Content-Type: application/json"   -d '{
    "url": "http://192.168.1.100:554",
    "store": "MAIN STORE"
  }'
```
