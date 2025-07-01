
# 📊 Camera Data API Documentation

All endpoints require a **JWT access token**.  
Camera identifiers may include: `_id`, `url`, `name`, `ids`, `urls`, `names`.

---

## 🔁 POST `/camera_data/all` — Full Camera Data

Returns full data document(s) for one or more cameras.

### 📤 Example Request
```json
{ "names": ["CAM 1", "CAM 2"] }
```

### ✅ Response
- Full merged camera data (hourly entries, regions).

---

## 📅 POST `/camera_data/list` — Data by Day(s)

Returns per-day totals for one or more cameras.

### 📤 Example Request
```json
{
  "name": "CAM 1",
  "days": ["17.06.2025", "18.06.2025"]
}
```

### ❌ Errors
- Missing `days`
- Invalid or future dates

---

## ⏱️ POST `/camera_data/time` — Data for Date + Time Range

Returns people count for a single day filtered by time.

### 📤 Example Request
```json
{
  "name": "CAM 1",
  "date": "17.06.2025",
  "startTime": "08:00",
  "endTime": "12:00"
}
```

### ❌ Errors
- Invalid date or time
- `startTime > endTime`

---

## 📆 POST `/camera_data/period` — Data Between Dates

Returns merged camera data between two dates.

### 📤 Example Request
```json
{
  "url": "rtsp://cam",
  "start": "12.06.2025",
  "end": "17.06.2025"
}
```

### ❌ Errors
- Invalid dates or future `end`
- Missing `start`

---

## 📚 POST `/camera_data/days_time` — Data by Days + Shared Time

Returns data for many days using the same time window.

### 📤 Example Request
```json
{
  "name": "CAM 1",
  "days": ["17.06.2025", "18.06.2025"],
  "startTime": "09:00",
  "endTime": "11:00"
}
```

---

### 🧪 Curl Example
```bash
curl -X POST http://localhost:5000/camera_data/list \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "name": "CAM 1", "days": ["17.06.2025"] }'
```

---
