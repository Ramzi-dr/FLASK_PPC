
# 📘 User Management API Documentation

All routes require a valid **JWT access token**.

---

## ➕ POST `/users` — Create New User

Create a new user account with email, password, and optional metadata.

### 🔐 Headers
- `Authorization: Bearer <TOKEN>`
- `Content-Type: application/json`

### 📤 Request Body
```json
{
  "email": "user@example.com",
  "password": "Pass1234",
  "clientID": "CLIENT1",
  "name": "John Doe",
  "tel": "12345678",
  "address": "Zurich"
}
```

### ✅ Success Response
- Code: `201 Created`
```json
{
  "msg": "✅ User created",
  "user": {
    "email": "USER@EXAMPLE.COM",
    "clientID": "CLIENT1",
    "name": "JOHN DOE",
    "tel": "12345678",
    "address": "ZURICH",
    "stores": []
  }
}
```

### ❌ Error Responses
- `400 Bad Request`: Missing fields, bad email format, weak password
- `409 Conflict`: Email already exists

---

## 📥 GET `/users` — List All Users

Retrieve all user accounts (excluding passwords).

### 🔐 Headers
- `Authorization: Bearer <TOKEN>`

### ✅ Success Response
- Code: `200 OK`
```json
{
  "users": [
    {
      "email": "USER1@EXAMPLE.COM",
      "clientID": "CLIENT1",
      "name": "JOHN DOE",
      "tel": "12345678",
      "address": "ZURICH",
      "stores": []
    }
  ]
}
```

### ❌ Error Responses
- `500 Internal Server Error`

---

## 🔄 PUT `/users` — Update User

Update user info, change password or email.

### 🔐 Headers
- `Authorization: Bearer <TOKEN>`
- `Content-Type: application/json`

### 🔁 Update Examples

**Update fields:**
```json
{
  "email": "USER@EXAMPLE.COM",
  "name": "Jane Smith",
  "tel": "98765432"
}
```

**Change password:**
```json
{
  "email": "USER@EXAMPLE.COM",
  "password": "NewPass123",
  "old_password": "OldPass123"
}
```

**Change email:**
```json
{
  "email": "USER@EXAMPLE.COM",
  "new_email": "NEW@EXAMPLE.COM"
}
```

### ✅ Success Response
```json
{
  "msg": "✅ User updated",
  "user": {
    "email": "NEW@EXAMPLE.COM",
    ...
  }
}
```

### ❌ Error Responses
- `400`: Missing email, weak password, invalid format
- `404`: User not found
- `409`: Email already exists
- `200`: No valid fields to update

---

## 🔴 DELETE `/users` — Delete User(s)

Delete one or more users and remove them from all store references.

### 🔐 Headers
- `Authorization: Bearer <TOKEN>`
- `Content-Type: application/json`

### 🧪 Request Body
```json
{
  "emails": ["USER@EXAMPLE.COM", "OTHER@EXAMPLE.COM"],
  "force": true
}
```

### ✅ Success Response
```json
{
  "msg": "✅ Deleted: USER@EXAMPLE.COM. ❌ Not found: MISSING@EXAMPLE.COM"
}
```

### ❌ Error Responses
- `400`: Missing emails, missing `force`
- `500`: Internal server error

---

