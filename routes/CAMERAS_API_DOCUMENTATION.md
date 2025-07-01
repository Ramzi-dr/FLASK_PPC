
# 🎥 Camera Management API Documentation

All endpoints require a **JWT access token**.

---

## 📥 GET `/cameras` — List All Cameras

Returns all cameras with ID, URL, username, name, stores, and data ID (password excluded).

### ✅ Response
```json
[
  {
    "_id": "CAMERA_ID",
    "url": "RTSP://IP/STREAM",
    "username": "admin",
    "name": "DOOR1",
    "stores": ["STORE1"],
    "data_id": "CAMERA_DATA_ID"
  }
]
```

---

## ➕ POST `/cameras` — Create Camera

Creates a new camera with optional store assignment and auto-generates a data document.

### 📤 Request Body
```json
{
  "url": "rtsp://192.168.1.1/stream",
  "username": "admin",
  "password": "123456",
  "store": "Store1",
  "name": "FrontDoor"
}
```

### ✅ Success Response
```json
{
  "msg": "✅ Camera created",
  "camera": {
    "_id": "ID",
    "url": "RTSP://192.168.1.1/STREAM",
    "username": "admin",
    "name": "FRONTDOOR",
    "stores": ["STORE1"],
    "data_id": "ID"
  }
}
```

### ❌ Errors
- `400`: Missing required fields, invalid URL
- `409`: Camera with URL already exists
- `404`: Store not found

---

## 🔄 PUT `/cameras` — Update Camera

Update camera's name, username, password, or URL.

### 📤 Request Body
```json
{
  "url": "rtsp://192.168.1.1/stream",
  "new_url": "rtsp://192.168.1.2/stream",
  "name": "UpdatedCam",
  "username": "admin2",
  "password": "newpass"
}
```

### ✅ Response
```json
{
  "msg": "✅ Camera updated",
  "camera": {
    "_id": "ID",
    "url": "RTSP://192.168.1.2/STREAM",
    "username": "admin2",
    "name": "UPDATEDCAM",
    "stores": ["STORE1"],
    "data_id": "ID"
  }
}
```

### ❌ Errors
- `400`: No valid fields, store update disallowed here
- `404`: Camera not found
- `409`: New URL already exists

---

## 🔴 DELETE `/cameras` — Delete Camera

Deletes camera, its associated data, and removes it from store(s).

### 📤 Request Body
```json
{
  "url": "rtsp://192.168.1.1/stream"
}
```
or
```json
{
  "name": "CAMERA1"
}
```

### ✅ Response
```json
{
  "msg": "✅ Camera 'RTSP://192.168.1.1/STREAM' deleted successfully"
}
```

### ❌ Errors
- `400`: No URL or name given
- `404`: Camera not found
- `400`: Multiple matches by name

---

### 🧪 Curl Example
```bash
curl -X POST https://your-url/cameras \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "url": "rtsp://192.168.1.1", "username": "admin", "password": "pass", "store": "Store1", "name": "Door1" }'
```

---
