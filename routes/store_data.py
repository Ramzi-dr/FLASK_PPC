# routes/store_data.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from bson import ObjectId
from camera_data_manager import CameraDataManager
from logger import logger
from datetime import datetime, date

data_bp = Blueprint("store_data", __name__)


def parse_date(date_str):
    """Accepts 'DD.MM.YYYY' or 'YYYY-MM-DD' and returns a date object."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


@data_bp.route("/all", methods=["POST"])
@jwt_required()
def get_store_data_all():
    """
    POST /store_data/all

    Returns full people-counting data for all cameras in a store.

    Accepted identifiers:
      - store name (case-insensitive)
      - store clientID
      - store _id (Mongo ObjectId string)

    ✅ Example:
    curl -k -X POST http://localhost:5000/store_data/all \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"store": "STORE 2"}'
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Request body must be a JSON object"), 400

        store_ident = payload.get("store")
        if not store_ident or not isinstance(store_ident, str):
            return jsonify(msg="❌ Field 'store' must be a non-empty string"), 400

        # Normalize and attempt match
        store = None
        try:
            store = request.db.stores.find_one({"_id": ObjectId(store_ident)})
        except:
            ident = store_ident.strip().upper()
            store = request.db.stores.find_one(
                {"$or": [{"name": ident}, {"clientID": ident}]}
            )

        if not store:
            return jsonify(msg=f"❌ Store '{store_ident}' not found"), 404

        cameras = store.get("cameras", [])
        camera_ids = [ObjectId(cam["_id"]) for cam in cameras if "_id" in cam]

        if not camera_ids:
            return jsonify(msg=f"⚠️ Store '{store_ident}' has no cameras"), 200

        manager = CameraDataManager(request.db)
        result = manager.get_all_data(camera_ids)
        return jsonify(result)

    except Exception as e:
        logger.critical(f"POST /store_data/all failed: {e}")
        return jsonify(msg="❌ Internal server error"), 500


@data_bp.route("/day", methods=["POST"])
@jwt_required()
def get_store_data_by_day_or_days():
    """
    POST /store_data/day

    Returns per-day people-count data for all cameras in a store.

    Accepts:
      - "store": required, store _id, name, or clientID (str)
      - "day": optional, single date (str)
      - "days": optional, list of dates (list[str]),
                 format "DD.MM.YYYY" or "YYYY-MM-DD".

    If neither "day" nor "days" is provided → returns data for today.

    ✅ Example (multiple days):
    curl -k -X POST http://localhost:5000/store_data/day \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"store": "STORE 2", "days": ["17.06.2025", "2025-06-18"]}'

    ✅ Example (single day):
    curl -k -X POST http://localhost:5000/store_data/day \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"store": "STORE 2", "day": "2025-06-18"}'

    ✅ Example (no days):
    curl -k -X POST http://localhost:5000/store_data/day \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"store": "STORE 2"}'
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        store_ident = payload.get("store")
        raw_days = payload.get("days") or payload.get("day")

        if not store_ident or not isinstance(store_ident, str):
            return jsonify(msg="❌ Field 'store' must be a non-empty string"), 400

        # Normalize raw_days to list
        if raw_days is None:
            raw_days = [date.today().strftime("%Y-%m-%d")]
        elif isinstance(raw_days, str):
            raw_days = [raw_days]
        elif not isinstance(raw_days, list):
            return jsonify(msg="❌ 'days' must be a string or list of dates"), 400

        today = date.today()
        parsed_days = []
        for d in raw_days:
            d_obj = parse_date(d)
            if not d_obj:
                return jsonify(msg=f"❌ Invalid date format: {d}"), 400
            if d_obj > today:
                return jsonify(msg=f"❌ Date in future: {d}"), 400
            parsed_days.append(d_obj.strftime("%Y-%m-%d"))

        # Lookup store by _id or name/clientID
        store = None
        try:
            store = request.db.stores.find_one({"_id": ObjectId(store_ident)})
        except:
            ident = store_ident.strip().upper()
            store = request.db.stores.find_one(
                {"$or": [{"name": ident}, {"clientID": ident}]}
            )

        if not store:
            return jsonify(msg=f"❌ Store '{store_ident}' not found"), 404

        cameras = store.get("cameras", [])
        camera_ids = [ObjectId(cam["_id"]) for cam in cameras if "_id" in cam]

        if not camera_ids:
            return jsonify(msg=f"⚠️ Store '{store_ident}' has no cameras"), 200

        manager = CameraDataManager(request.db)
        result = manager.get_data_by_days(camera_ids, parsed_days)
        return jsonify(result)

    except Exception as e:
        logger.critical(f"POST /store_data/by_day failed: {e}")
        return jsonify(msg="❌ Internal server error"), 500


@data_bp.route("/time", methods=["POST"])
@jwt_required()
def get_store_data_by_time():
    """
    POST /store_data/time

    Returns people-count data for a store’s cameras on a specific date,
    filtered by optional start and end time.

    Required fields:
      - "store": store name, _id, or clientID
      - "date": string in "DD.MM.YYYY" or "YYYY-MM-DD"
    
    Optional:
      - "startTime": default = "00:00"
      - "endTime": default = "23:59"

    ✅ Example:
    curl -k -X POST http://localhost:5000/store_data/time \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"store": "STORE 2", "date": "2025-06-17", "startTime": "08:00", "endTime": "12:00"}'
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        store_ident = payload.get("store")
        date_str = payload.get("date")
        if not store_ident or not isinstance(store_ident, str):
            return jsonify(msg="❌ Field 'store' must be a non-empty string"), 400
        if not date_str:
            return jsonify(msg="❌ Missing 'date' field"), 400

        date_obj = parse_date(date_str)
        if not date_obj or date_obj > date.today():
            return jsonify(msg=f"❌ Invalid or future date: {date_str}"), 400
        iso_day = date_obj.strftime("%Y-%m-%d")

        # Parse time range
        start_str = payload.get("startTime", "00:00")
        end_str = payload.get("endTime", "23:59")
        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            if start_time > end_time:
                return jsonify(msg="❌ startTime must be before endTime"), 400
        except ValueError:
            return jsonify(msg="❌ Invalid time format (HH:MM required)"), 400

        # Find store
        store = None
        try:
            store = request.db.stores.find_one({"_id": ObjectId(store_ident)})
        except:
            ident = store_ident.strip().upper()
            store = request.db.stores.find_one(
                {"$or": [{"name": ident}, {"clientID": ident}]}
            )

        if not store:
            return jsonify(msg=f"❌ Store '{store_ident}' not found"), 404

        cameras = store.get("cameras", [])
        camera_ids = [ObjectId(cam["_id"]) for cam in cameras if "_id" in cam]

        if not camera_ids:
            return jsonify(msg=f"⚠️ Store '{store_ident}' has no cameras"), 200

        manager = CameraDataManager(request.db)
        result = manager.get_data_by_time_range(
            camera_ids, iso_day, start_time, end_time
        )
        return jsonify(result)

    except Exception as e:
        logger.critical(f"POST /store_data/time failed: {e}")
        return jsonify(msg="❌ Internal server error"), 500


@data_bp.route("/period", methods=["POST"])
@jwt_required()
def get_store_data_by_period():
    """
    POST /store_data/period

    Returns people-count data for all cameras of a store, between a start and end date (inclusive).

    Required fields:
      - "store": store name, _id, or clientID
      - "start": date string in "DD.MM.YYYY" or "YYYY-MM-DD"

    Optional:
      - "end": date string (defaults to today)

    ✅ Example:
    curl -k -X POST http://localhost:5000/store_data/period \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"store": "STORE 2", "start": "10.06.2025", "end": "17.06.2025"}'
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        store_ident = payload.get("store")
        start_str = payload.get("start")
        end_str = payload.get("end")

        if not store_ident or not isinstance(store_ident, str):
            return jsonify(msg="❌ Field 'store' must be a non-empty string"), 400
        if not start_str:
            return jsonify(msg="❌ Missing 'start' date"), 400

        start_dt = parse_date(start_str)
        end_dt = parse_date(end_str) if end_str else date.today()

        if not start_dt or start_dt > date.today():
            return jsonify(msg=f"❌ Invalid or future start date: {start_str}"), 400
        if end_str and not end_dt:
            return jsonify(msg=f"❌ Invalid 'end' date: {end_str}"), 400
        if end_dt > date.today():
            return jsonify(msg=f"❌ 'end' date cannot be in the future: {end_str}"), 400
        if end_dt < start_dt:
            return jsonify(msg="❌ 'end' date must not precede 'start'"), 400

        # Find store
        store = None
        try:
            store = request.db.stores.find_one({"_id": ObjectId(store_ident)})
        except:
            ident = store_ident.strip().upper()
            store = request.db.stores.find_one(
                {"$or": [{"name": ident}, {"clientID": ident}]}
            )

        if not store:
            return jsonify(msg=f"❌ Store '{store_ident}' not found"), 404

        cameras = store.get("cameras", [])
        camera_ids = [ObjectId(cam["_id"]) for cam in cameras if "_id" in cam]

        if not camera_ids:
            return jsonify(msg=f"⚠️ Store '{store_ident}' has no cameras"), 200

        manager = CameraDataManager(request.db)
        result = manager.get_data_by_period(camera_ids, start_dt, end_dt)
        return jsonify(result)

    except Exception as e:
        logger.critical(f"POST /store_data/period failed: {e}")
        return jsonify(msg="❌ Internal server error"), 500


@data_bp.route("/days_time", methods=["POST"])
@jwt_required()
def store_data_days_time():
    """
    POST /store_data/days_time

    Returns people-count data for a store's cameras on specific days,
    optionally filtered by time range.

    Required:
    - "store": store name, _id, or clientID
    - "days": list of dates (DD.MM.YYYY or YYYY-MM-DD)

    Optional:
    - "startTime": time string in "HH:MM" (default: "00:00")
    - "endTime": time string in "HH:MM" (default: "23:59")

    Returns:
    - JSON with day-wise filtered data or error message
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        store_ident = payload.get("store")
        days = payload.get("days")
        if not store_ident or not isinstance(days, list) or not days:
            return jsonify(msg="❌ 'store' and non-empty 'days' list required"), 400

        # Parse and validate each date
        today = date.today()
        parsed_days = []
        for d in days:
            dt_obj = parse_date(d)
            if not dt_obj:
                return jsonify(msg=f"❌ Invalid date: {d}"), 400
            if dt_obj > today:
                return jsonify(msg=f"❌ Date in future: {d}"), 400
            parsed_days.append(dt_obj.strftime("%Y-%m-%d"))

        # Validate and parse start/end times
        start_str = payload.get("startTime", "00:00")
        end_str = payload.get("endTime", "23:59")
        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            if start_time > end_time:
                return jsonify(msg="❌ startTime must be before endTime"), 400
        except ValueError:
            return jsonify(msg="❌ Time format must be HH:MM"), 400

        # Build store query safely (exclude None)
        store_query = []
        if ObjectId.is_valid(store_ident):
            store_query.append({"_id": ObjectId(store_ident)})
        store_query.append({"name": store_ident.strip().upper()})
        store_query.append({"clientID": store_ident.strip().upper()})

        store = request.db.stores.find_one({"$or": store_query})

        if not store or "cameras" not in store or not store["cameras"]:
            return (
                jsonify(msg=f"❌ Store '{store_ident}' not found or has no cameras"),
                404,
            )

        cam_ids = [ObjectId(c["_id"]) for c in store["cameras"] if "_id" in c]
        if not cam_ids:
            return (
                jsonify(msg=f"❌ No valid camera IDs found in store '{store_ident}'"),
                404,
            )

        manager = CameraDataManager(request.db)
        result = manager.get_data_days_with_time_range(
            cam_ids, parsed_days, start_time, end_time
        )
        return jsonify(result)

    except Exception as exc:
        logger.critical(f"/store_data/days_time failed: {exc}")
        return (
            jsonify(
                msg="❌ Internal error. Example body: { 'store':'STORE 2','days':['17.06.2025'],'startTime':'08:00' }"
            ),
            500,
        )


def init_store_data_routes(db):
    @data_bp.before_request
    def inject_db():
        request.db = db
