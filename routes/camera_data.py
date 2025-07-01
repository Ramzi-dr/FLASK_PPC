# camera_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, date
from bson import ObjectId
from camera_data_manager import CameraDataManager
from logger import logger


data_bp = Blueprint("camera_data", __name__)


# ──────────────────────────────────────────────────────────────
# Utility helpers
# ──────────────────────────────────────────────────────────────
def parse_date(date_str):
    """
    Convert either 'DD.MM.YYYY' or 'YYYY-MM-DD' to a date object.
    Returns None if the format is invalid.
    """
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def validate_and_get_camera_ids(identifiers, db):
    """
    Accepts a single identifier (_id, url, or name) or a list of them.
    Resolves all to valid ObjectIds, skips invalids.
    Returns list of ObjectIds.
    """
    if not isinstance(identifiers, list):
        identifiers = [identifiers]
    result = []
    for ident in identifiers:
        try:
            result.append(ObjectId(ident))
        except Exception:
            ident_norm = ident.strip().upper()
            cam = db.cameras.find_one(
                {"$or": [{"url": ident_norm}, {"name": ident_norm}]}
            )
            if cam:
                result.append(cam["_id"])
    return result


# ──────────────────────────────────────────────────────────────
# /all – Return full documents for one or more cameras
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# /all – full payload for 1 or many cameras (merged or raw)
# ──────────────────────────────────────────────────────────────
@data_bp.route("/all", methods=["POST"])
@jwt_required()
def get_all_data():
    """
    POST /camera_data/all

    Deep explanation:
    ------------------
    This endpoint returns the full people-counting document(s) for one or more cameras.

    You may provide a camera using one of:
      - "_id", "url", "name"   → for single camera
      - "ids", "urls", "names" → for multiple cameras

    For multiple cameras, the hourly entries are merged:
      - Same hour = counters summed
      - Unique hour = added as-is
      - RegionList["Region"] with same ID = counts summed
      - RegionList["Region"] with different ID = added

    ✅ Examples:

    curl -k -X POST http://localhost:5000/camera_data/all \
         -H "Authorization: Bearer <JWT>" \
         -H "Content-Type: application/json" \
         -d '{"name": "CAM 1"}'

    curl -k -X POST http://localhost:5000/camera_data/all \
         -H "Authorization: Bearer <JWT>" \
         -H "Content-Type: application/json" \
         -d '{"names": ["CAM 1", "CAM 2"]}'

    ❌ Errors:
      - Empty or malformed body: 400
      - No valid cameras matched: 404
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        identifiers = (
            payload.get("_id")
            or payload.get("url")
            or payload.get("name")
            or payload.get("ids")
            or payload.get("urls")
            or payload.get("names")
        )
        if not identifiers:
            return jsonify(msg="❌ Provide one or more camera identifiers"), 400

        camera_ids = validate_and_get_camera_ids(identifiers, request.db)
        if not camera_ids:
            return jsonify(msg="❌ No valid cameras found"), 404

        manager = CameraDataManager(request.db)
        data = manager.get_all_data(camera_ids)

        return jsonify(data)

    except Exception as exc:
        logger.critical(f"POST /all failed: {exc}")
        return jsonify(msg="❌ Internal server error"), 500


# ──────────────────────────────────────────────────────────────
# /list – Get data for days from one or more cameras
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# /list – return people-count per day for 1 or more cameras
# ──────────────────────────────────────────────────────────────
@data_bp.route("/list", methods=["POST"])
@jwt_required()
def get_data_by_days():
    """
    POST /camera_data/list

    Deep explanation:
    This route returns per-day people count data for one or more cameras.
    You must supply a list of valid days and at least one camera identifier.

    Supported identifiers:
      - "_id", "url", "name" for single cam
      - "ids", "urls", "names" for multiple

    ✅ Examples:
    curl -k -X POST http://localhost:5000/camera_data/list \
         -H "Authorization: Bearer <JWT>" \
         -H "Content-Type: application/json" \
         -d '{"names": ["CAM 1", "CAM 2"], "days": ["17.06.2025"]}'
         -d '{ "name": "CAM 4", "days":["19.06.2025"]}'

    ❌ Examples:
    - Missing days → 400
    - Invalid date → 400
    - Camera not found → 404
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        identifiers = (
            payload.get("_id")
            or payload.get("url")
            or payload.get("name")
            or payload.get("ids")
            or payload.get("urls")
            or payload.get("names")
        )
        raw_days = payload.get("days")

        if not identifiers or not isinstance(raw_days, list) or not raw_days:
            return jsonify(msg="❌ Provide 'days' and camera identifier(s)"), 400

        today = date.today()
        parsed_days = []
        for d in raw_days:
            d_obj = parse_date(d)
            if not d_obj:
                return jsonify(msg=f"❌ Invalid date: {d}"), 400
            if d_obj > today:
                return jsonify(msg=f"❌ Date in future: {d}"), 400
            parsed_days.append(d_obj.strftime("%Y-%m-%d"))

        camera_ids = validate_and_get_camera_ids(identifiers, request.db)
        if not camera_ids:
            return jsonify(msg="❌ No valid cameras found"), 404

        manager = CameraDataManager(request.db)
        result = manager.get_data_by_days(camera_ids, parsed_days)
        return jsonify(result)

    except Exception as exc:
        logger.critical(f"POST /list failed: {exc}")
        return jsonify(msg="❌ Internal server error"), 500


# ──────────────────────────────────────────────────────────────
# /time – return people-count data filtered by time on a date
# ──────────────────────────────────────────────────────────────
@data_bp.route("/time", methods=["POST"])
@jwt_required()
def get_data_by_time():
    """
    POST /camera_data/time

    Deep Explanation:
    ------------------
    This endpoint returns people-count data for a specific date, filtered by time window.
    The user must provide:
      - A camera or list of cameras using: _id, url, name, ids, urls, names
      - A valid date in 'DD.MM.YYYY' or 'YYYY-MM-DD'
      - Optional startTime and endTime in 'HH:MM'

    ✅ Supports single or multi-camera merge
    ❌ Rejects future dates, invalid format, or startTime > endTime

    curl -k -X POST http://localhost:5000/camera_data/time \
         -H "Authorization: Bearer <TOKEN>" \
         -H "Content-Type: application/json" \
         -d '{"names": ["CAM 1", "CAM 2"], "date": "17.06.2025", "startTime": "08:00", "endTime": "12:00"}'
    """
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        identifiers = (
            payload.get("_id")
            or payload.get("url")
            or payload.get("name")
            or payload.get("ids")
            or payload.get("urls")
            or payload.get("names")
        )
        if not identifiers:
            return jsonify(msg="❌ Provide camera identifier(s)"), 400

        raw_date = payload.get("date")
        if not raw_date:
            return jsonify(msg="❌ Provide 'date' field"), 400

        date_obj = parse_date(raw_date)
        if not date_obj or date_obj > date.today():
            return jsonify(msg="❌ Invalid or future 'date'"), 400

        start_str = payload.get("startTime", "00:00")
        end_str = payload.get("endTime", "23:59")
        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            if start_time > end_time:
                return jsonify(msg="❌ startTime must be before endTime"), 400
        except ValueError:
            return jsonify(msg="❌ Time format must be HH:MM"), 400

        camera_ids = validate_and_get_camera_ids(identifiers, request.db)
        if not camera_ids:
            return jsonify(msg="❌ No valid cameras found"), 404

        manager = CameraDataManager(request.db)
        result = manager.get_data_by_time_range(
            camera_ids, date_obj.strftime("%Y-%m-%d"), start_time, end_time
        )
        return jsonify(result)

    except Exception as exc:
        logger.critical(f"POST /time failed: {exc}")
        return jsonify(msg="❌ Internal server error"), 500


# ──────────────────────────────────────────────────────────────
# /period – inclusive date window
# ──────────────────────────────────────────────────────────────
@data_bp.route("/period", methods=["POST"])
@jwt_required()
def get_data_period():
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        identifiers = (
            payload.get("_id")
            or payload.get("url")
            or payload.get("name")
            or payload.get("ids")
            or payload.get("urls")
            or payload.get("names")
        )
        start_str = payload.get("start")
        end_str = payload.get("end")

        if not identifiers or not start_str:
            return jsonify(msg="❌ Provide 'start' date and camera identifier(s)"), 400

        start = parse_date(start_str)
        end = parse_date(end_str) if end_str else date.today()

        if not start or start > date.today():
            return jsonify(msg="❌ Invalid or future 'start'"), 400
        if end_str and not end:
            return jsonify(msg="❌ Invalid 'end' format"), 400
        if end > date.today():
            return jsonify(msg="❌ 'end' date cannot be in the future"), 400
        if end < start:
            return jsonify(msg="❌ 'end' must not precede 'start'"), 400

        camera_ids = validate_and_get_camera_ids(identifiers, request.db)
        if not camera_ids:
            return jsonify(msg="❌ No valid cameras found"), 404

        manager = CameraDataManager(request.db)
        result = manager.get_data_by_period(
            camera_ids, start_str, end_str or date.today().strftime("%d.%m.%Y")
        )
        return jsonify(result)

    except Exception as exc:
        logger.critical(f"POST /period failed: {exc}")
        return (
            jsonify(
                msg=(
                    "❌ Invalid request. Example body: "
                    "{'name':'CAM 1','start':'10.06.2025','end':'17.06.2025'}"
                )
            ),
            400,
        )


# ──────────────────────────────────────────────────────────────
# /days_time – multiple dates with a shared time window
# ──────────────────────────────────────────────────────────────
@data_bp.route("/days_time", methods=["POST"])
@jwt_required()
def get_data_by_days_and_time():
    try:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(msg="❌ Body must be JSON object"), 400

        identifiers = (
            payload.get("_id")
            or payload.get("url")
            or payload.get("name")
            or payload.get("ids")
            or payload.get("urls")
            or payload.get("names")
        )
        if not identifiers:
            return jsonify(msg="❌ Provide camera identifier(s)"), 400

        days = payload.get("days")
        if not isinstance(days, list) or not days:
            return jsonify(msg="❌ 'days' must be a non-empty list"), 400

        today = date.today()
        parsed_days = []
        for d in days:
            dt = parse_date(d)
            if not dt:
                return jsonify(msg=f"❌ Invalid date: {d}"), 400
            if dt > today:
                return jsonify(msg=f"❌ Date in future: {d}"), 400
            parsed_days.append(dt.strftime("%Y-%m-%d"))

        start_str = payload.get("startTime", "00:00")
        end_str = payload.get("endTime", "23:59")
        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            if start_time > end_time:
                return jsonify(msg="❌ startTime must be before endTime"), 400
        except ValueError:
            return jsonify(msg="❌ Time format must be HH:MM"), 400

        camera_ids = validate_and_get_camera_ids(identifiers, request.db)
        if not camera_ids:
            return jsonify(msg="❌ No valid cameras found"), 404

        manager = CameraDataManager(request.db)
        result = manager.get_data_days_with_time_range(
            camera_ids, parsed_days, start_time, end_time
        )
        return jsonify(result)

    except Exception as exc:
        logger.critical(f"POST /days_time failed: {exc}")
        return (
            jsonify(
                msg=(
                    "❌ Internal error. Example body: "
                    "{ 'name':'CAM 1','days':['17.06.2025'],'startTime':'08:00'}"
                )
            ),
            500,
        )


# ──────────────────────────────────────────────────────────────
# Inject DB into every request context
# ──────────────────────────────────────────────────────────────
def init_camera_data_routes(db):
    """
    Call this from your app factory to register routes and
    make the MongoDB handle available on `request.db`.
    """

    @data_bp.before_request
    def inject_db():
        request.db = db
