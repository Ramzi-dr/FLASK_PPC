"""
admin.py — Admin blueprint to update JWT token expiry securely and flexibly

This blueprint provides a protected route to dynamically change
access and refresh token expiration times during runtime.

Security features:
- Requires HTTP Basic Auth with username and bcrypt-hashed password
  loaded from your database environment variables.
- Access allowed **only from localhost** (127.0.0.1 or ::1)
- Rejects remote IPs with clear message: "You are using a remote machine and this is only allowed from localhost"
- Validates and converts user-friendly time inputs (seconds, minutes, hours, days) to seconds
- Updates global app config for token expirations and forces old token invalidation immediately

Usage example from localhost shell (replace admin password accordingly):

curl -u AdminHS:yourpassword -X POST http://127.0.0.1:5000/admin/set_token_expiry \
  -H "Content-Type: application/json" \
  -d '{"access_minute":3,"refresh_hour":2}'

This sets access tokens to expire in 3 minutes (180 seconds) and refresh tokens in 2 hours (7200 seconds),
and invalidates all previously issued tokens to enforce new expirations immediately.
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from datetime import datetime, timezone, timedelta
import bcrypt

admin_bp = Blueprint("admin", __name__)
env_collection = None  # will be initialized from main app


def init_admin_routes(db):
    global env_collection
    env_collection = db["env"]


def basic_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            return jsonify(msg="❌ Missing or invalid authentication"), 401, {"WWW-Authenticate": 'Basic realm="Login required"'}

        # Fetch admin credentials directly from env collection
        user_doc = env_collection.find_one({"key": "FLASK_USER"})
        pw_doc = env_collection.find_one({"key": "FLASK_PASSWORD"})

        if not user_doc or not pw_doc:
            return jsonify(msg="❌ Admin credentials not found in database"), 500

        if auth.username != user_doc["value"]:
            return jsonify(msg="❌ Invalid username or password"), 403

        if not bcrypt.checkpw(auth.password.encode(), pw_doc["value"].encode()):
            return jsonify(msg="❌ Invalid username or password"), 403

        return fn(*args, **kwargs)
    return wrapper



def local_only(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(msg="❌ You are using a remote machine and this is only allowed from localhost"), 403
        return fn(*args, **kwargs)
    return wrapper


def time_to_seconds(data, prefix):
    """
    Converts a time specification from data dict into seconds.
    Accepts keys like 'second', 'minute', 'hour', 'day' prefixed by prefix.
    Returns total seconds or None if no valid input.
    """
    multipliers = {
        'second': 1,
        'minute': 60,
        'hour': 3600,
        'day': 86400
    }
    total = 0
    found = False
    for unit, mult in multipliers.items():
        key = f"{prefix}_{unit}"
        if key in data:
            try:
                val = int(data[key])
                if val < 0:
                    return None  # negative invalid
                total += val * mult
                found = True
            except (ValueError, TypeError):
                return None  # invalid int conversion
    return total if found else None


@admin_bp.route("/set_token_expiry", methods=["POST"])
@basic_auth_required
@local_only
def set_token_expiry():
    data = request.get_json(force=True) or {}

    access_seconds = time_to_seconds(data, "access")
    refresh_seconds = time_to_seconds(data, "refresh")

    if access_seconds is None and refresh_seconds is None:
        return jsonify(msg="❌ Must provide at least one valid access_* or refresh_* time parameter (second/minute/hour/day)"), 400

    if access_seconds is not None:
        current_app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=access_seconds)
        env_collection.update_one(
            {"key": "JWT_ACCESS_TOKEN_EXPIRES_SECONDS"},
            {"$set": {"value": str(access_seconds)}}
        )

    if refresh_seconds is not None:
        current_app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=refresh_seconds)
        env_collection.update_one(
            {"key": "JWT_REFRESH_TOKEN_EXPIRES_SECONDS"},
            {"$set": {"value": str(refresh_seconds)}}
        )

    current_app.config["TOKEN_ISSUED_AFTER"] = datetime.now(tz=timezone.utc).timestamp()

    return jsonify(
        msg="✅ Token expiry updated and old tokens invalidated",
        access_token_expires_seconds=access_seconds,
        refresh_token_expires_seconds=refresh_seconds
    )
