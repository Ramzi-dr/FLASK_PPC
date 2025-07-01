
# 📦 Store Data API Documentation (Full Detail)

All endpoints require a valid **JWT access token**.  
You can identify a store using its `name`, `clientID`, or Mongo `_id`.

---

## 🔁 POST `/store_data/all` — Full Data for Store

Returns complete people-counting data from **all cameras** in the selected store.

### ✅ Example
```bash
curl -k -X POST http://localhost:5000/store_data/all \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "store": "STORE 2" }'
```

### ❌ Error Cases
- `400` → Missing store field or wrong type
- `404` → Store not found
- `200` → Store found, but has no cameras

---

## 📅 POST `/store_data/day` — Daily Summary (Single or Multiple)

Returns per-day totals for a store's cameras.

### 🧪 Examples
```bash
# One specific date
curl -k -X POST http://localhost:5000/store_data/day \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{ "store": "STORE 2", "day": "2025-06-17" }'

# Multiple dates
curl -k -X POST http://localhost:5000/store_data/day \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{ "store": "STORE 2", "days": ["17.06.2025", "2025-06-18"] }'

# Default (today)
curl -k -X POST http://localhost:5000/store_data/day \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{ "store": "STORE 2" }'
```

### ❌ Error Cases
- `400` → Invalid date(s), future date(s), or wrong input format
- `404` → Store not found

---

## ⏱️ POST `/store_data/time` — Data for a Specific Day + Time Window

Returns per-hour data for all store cameras filtered by time.

### ✅ Example
```bash
curl -k -X POST http://localhost:5000/store_data/time \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{ "store": "STORE 2", "date": "2025-06-17", "startTime": "08:00", "endTime": "12:00" }'
```

### ❌ Error Cases
- `400` → Missing or invalid date/time
- `404` → Store not found

---

## 📆 POST `/store_data/period` — Inclusive Date Range

Returns merged people-count totals across a range of days.

### ✅ Example
```bash
curl -k -X POST http://localhost:5000/store_data/period \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{ "store": "STORE 2", "start": "10.06.2025", "end": "17.06.2025" }'
```

### ❌ Error Cases
- `400` → Missing start, invalid formats, future dates, end < start
- `404` → Store not found

---

## 📚 POST `/store_data/days_time` — Days + Shared Time Filter

Returns filtered data for multiple days with one shared time window.

### ✅ Example
```bash
curl -k -X POST http://localhost:5000/store_data/days_time \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
        "store": "STORE 2",
        "days": ["17.06.2025", "18.06.2025"],
        "startTime": "09:00",
        "endTime": "11:00"
      }'
```

### ❌ Error Cases
- `400` → Missing `days`, invalid time format, start > end
- `404` → Store or camera IDs not found

---
