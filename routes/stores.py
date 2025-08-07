"stores.py"

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt
from collections import OrderedDict
import re
import json
from logger import logger  # ✅ Import custom logger

stores_bp = Blueprint("stores", __name__)

email_regex = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$")
TIME_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def init_store_routes(db):

    @stores_bp.route("/stores", methods=["GET"])
    @jwt_required()
    def get_stores():
        try:
            stores = []
            for doc in db.stores.find({}):
                doc.pop(
                    "_id", None
                )  # ✅ Remove ObjectId to avoid JSON serialization issues
                ordered = OrderedDict()
                ordered["name"] = doc.get("name", "")
                ordered["clientID"] = doc.get("clientID", "")
                ordered["address"] = doc.get("address", "")
                ordered["users"] = doc.get("users", [])
                ordered["open_time"] = doc.get("open_time", "00:00")
                ordered["close_time"] = doc.get("close_time", "23:59")

                converted_cameras = []
                for cam in doc.get("cameras", []):
                    if isinstance(cam, dict):
                        cam = cam.copy()
                        if "_id" in cam:
                            cam["_id"] = str(cam["_id"])
                        if "name" not in cam:
                            cam["name"] = ""
                        converted_cameras.append(cam)
                    else:
                        converted_cameras.append(cam)

                ordered["cameras"] = converted_cameras
                stores.append(ordered)

            logger.info("Returned all stores successfully")
            return Response(json.dumps({"stores": stores}), mimetype="application/json")
        except Exception as e:
            logger.critical(f"GET /stores failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @stores_bp.route("/stores", methods=["POST"])
    @jwt_required()
    def create_store():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict) or data == {}:
                return jsonify(msg="❌ Body cannot be empty"), 400

            name = data.get("name", "").strip().upper()
            if not name:
                return jsonify(msg="❌ 'name' is required"), 400
            if db.stores.find_one({"name": name}):
                return jsonify(msg=f"❌ Store with name '{name}' already exists"), 409

            clientID = data.get("clientID", "").strip().upper()
            address = data.get("address", "").strip().upper()

            users = data.get("users", [])
            if not isinstance(users, list):
                return jsonify(msg="❌ 'users' must be a list of emails"), 400

            open_time = data.get("open_time", "").strip()
            close_time = data.get("close_time", "").strip()

            def is_valid_24h_time(t):
                return bool(re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t))

            if close_time and not open_time:
                return (
                    jsonify(
                        msg="❌ 'open_time' is required if 'close_time' is provided"
                    ),
                    400,
                )

            if open_time and not close_time:
                close_time = "23:59"

            if not open_time and not close_time:
                open_time = "00:00"
                close_time = "23:59"

            if not is_valid_24h_time(open_time):
                return (
                    jsonify(
                        msg="❌ 'open_time' must be in HH:MM 24-hour format (00:00 to 23:59)"
                    ),
                    400,
                )
            if not is_valid_24h_time(close_time):
                return (
                    jsonify(
                        msg="❌ 'close_time' must be in HH:MM 24-hour format (00:00 to 23:59)"
                    ),
                    400,
                )

            open_hour, open_min = map(int, open_time.split(":"))
            close_hour, close_min = map(int, close_time.split(":"))
            if (open_hour, open_min) >= (close_hour, close_min):
                return (
                    jsonify(msg="❌ 'open_time' must be earlier than 'close_time'"),
                    400,
                )

            clean_users = []
            missing_users = []
            for email in users:
                if not isinstance(email, str) or not email.strip():
                    continue
                upper_email = email.strip().upper()
                if not email_regex.match(upper_email):
                    return jsonify(msg=f"❌ Invalid email format: {email}"), 400
                user_doc = db.users.find_one({"email": upper_email})
                if user_doc:
                    clean_users.append(upper_email)
                else:
                    missing_users.append(upper_email)

            store = {
                "name": name,
                "clientID": clientID,
                "address": address,
                "users": clean_users,
                "cameras": [],
                "open_time": open_time,
                "close_time": close_time,
            }

            insert_result = db.stores.insert_one(store)
            new_store = db.stores.find_one({"_id": insert_result.inserted_id})
            new_store.pop("_id", None)  # ✅ remove ObjectId before returning

            for user_email in clean_users:
                db.users.update_one(
                    {"email": user_email}, {"$addToSet": {"stores": name}}
                )

            ordered_store = OrderedDict()
            for field in [
                "name",
                "clientID",
                "address",
                "users",
                "cameras",
                "open_time",
                "close_time",
            ]:
                ordered_store[field] = new_store.get(
                    field, "" if field != "users" else []
                )

            msg = "✅ Store created."
            if missing_users:
                msg += f" Non-existing users ignored: {', '.join(missing_users)}. Please create them first in the users endpoint."

            logger.info(f"Created store '{name}'")
            if missing_users:
                logger.warning(
                    f"Missing users when creating store '{name}': {missing_users}"
                )

            return (
                Response(
                    json.dumps({"msg": msg, "store": ordered_store}),
                    mimetype="application/json",
                ),
                201,
            )
        except Exception as e:
            logger.critical(f"POST /stores failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @stores_bp.route("/stores", methods=["PUT"])
    @jwt_required()
    def update_store():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict) or data == {}:
                return jsonify(msg="❌ Body cannot be empty"), 400

            current_name = (
                data.get("name") or data.get("current_name") or data.get("old_name")
            )
            if not current_name or not isinstance(current_name, str):
                return (
                    jsonify(
                        msg="❌ 'name' or 'current_name' of the store to update is required"
                    ),
                    400,
                )
            current_name = current_name.strip().upper()

            existing_store = db.stores.find_one({"name": current_name})
            if not existing_store:
                return (
                    jsonify(msg=f"❌ Store with name '{current_name}' not found"),
                    404,
                )

            new_name = data.get("new_name")
            if new_name:
                if not isinstance(new_name, str) or not new_name.strip():
                    return jsonify(msg="❌ 'new_name' must be a non-empty string"), 400
                new_name = new_name.strip().upper()
                if new_name != current_name and db.stores.find_one({"name": new_name}):
                    return (
                        jsonify(msg=f"❌ Store with name '{new_name}' already exists"),
                        409,
                    )
            else:
                new_name = current_name

            disallowed_fields = {"users"}
            allowed_keys = set(existing_store.keys()) - {"_id", "users", "name"}

            update_fields = {}
            changes_made = []

            open_time = data.get("open_time")
            close_time = data.get("close_time")

            def is_valid_24h_time(t):
                return bool(re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t))

            if open_time and not is_valid_24h_time(open_time):
                return (
                    jsonify(
                        msg="❌ 'open_time' must be in HH:MM 24-hour format (00:00–23:59)"
                    ),
                    400,
                )
            if close_time and not is_valid_24h_time(close_time):
                return (
                    jsonify(
                        msg="❌ 'close_time' must be in HH:MM 24-hour format (00:00–23:59)"
                    ),
                    400,
                )

            final_open_time = open_time or existing_store.get("open_time")
            final_close_time = close_time or existing_store.get("close_time")

            if close_time and not final_open_time:
                return (
                    jsonify(
                        msg="❌ 'open_time' is required if 'close_time' is provided"
                    ),
                    400,
                )

            if final_open_time and final_close_time:
                oh, om = map(int, final_open_time.split(":"))
                ch, cm = map(int, final_close_time.split(":"))
                if (oh, om) >= (ch, cm):
                    return (
                        jsonify(msg="❌ 'open_time' must be earlier than 'close_time'"),
                        400,
                    )

            if open_time and open_time != existing_store.get("open_time"):
                update_fields["open_time"] = open_time
                changes_made.append("open_time")
            if close_time and close_time != existing_store.get("close_time"):
                update_fields["close_time"] = close_time
                changes_made.append("close_time")

            for key, value in data.items():
                key_lower = key.lower()
                if key_lower in {
                    "name",
                    "current_name",
                    "old_name",
                    "new_name",
                    "open_time",
                    "close_time",
                }:
                    continue
                if key_lower in disallowed_fields:
                    return (
                        jsonify(
                            msg=f"❌ Field '{key}' cannot be updated here. Use dedicated endpoints for users."
                        ),
                        400,
                    )
                if key_lower not in allowed_keys:
                    return (
                        jsonify(msg=f"❌ Field '{key}' is not allowed to be updated"),
                        400,
                    )

                new_val = value.strip().upper() if isinstance(value, str) else value
                if existing_store.get(key_lower) != new_val:
                    update_fields[key_lower] = new_val
                    changes_made.append(key_lower)

            if new_name != current_name:
                update_fields["name"] = new_name
                changes_made.append("name")

            if not changes_made:
                return jsonify(msg="ℹ️ No changes detected to update"), 200

            db.stores.update_one({"name": current_name}, {"$set": update_fields})

            if new_name != current_name:
                for user_email in existing_store.get("users", []):
                    db.users.update_one(
                        {"email": user_email}, {"$pull": {"stores": current_name}}
                    )
                    db.users.update_one(
                        {"email": user_email}, {"$addToSet": {"stores": new_name}}
                    )

            updated_store = db.stores.find_one({"name": new_name})
            if updated_store:
                clean_cams = []
                for cam in updated_store.get("cameras", []):
                    clean = {}
                    for k, v in cam.items():
                        clean[k] = str(v) if k == "_id" else v
                    clean_cams.append(clean)
                updated_store["cameras"] = clean_cams

            ordered_store = OrderedDict()
            for field in [
                "name",
                "clientID",
                "address",
                "users",
                "cameras",
                "open_time",
                "close_time",
            ]:
                ordered_store[field] = updated_store.get(
                    field, [] if field == "users" else ""
                )

            logger.info(f"Updated store '{current_name}' fields: {changes_made}")
            return (
                Response(
                    json.dumps(
                        {
                            "msg": f"✅ Store '{current_name}' updated",
                            "store": ordered_store,
                        }
                    ),
                    mimetype="application/json",
                ),
                200,
            )

        except Exception as e:
            logger.critical(f"PUT /stores failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @stores_bp.route("/stores", methods=["DELETE"])
    @jwt_required()
    def delete_store():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict) or data == {}:
                return jsonify(msg="❌ Body cannot be empty"), 400

            if data.get("force", False) is not True:
                return (
                    jsonify(msg="❌ You must confirm deletion with 'force': true"),
                    400,
                )

            names = data.get("name")
            if not names:
                return jsonify(msg="❌ 'name' field is required"), 400

            store_names = (
                [names.strip().upper()]
                if isinstance(names, str)
                else (
                    [str(n).strip().upper() for n in names if str(n).strip()]
                    if isinstance(names, list)
                    else None
                )
            )

            if not store_names:
                return (
                    jsonify(
                        msg="❌ 'name' must be a non-empty string or list of strings"
                    ),
                    400,
                )

            deleted, not_found = [], []

            for store_name in store_names:
                if db.stores.find_one({"name": store_name}):
                    db.users.update_many(
                        {"stores": store_name}, {"$pull": {"stores": store_name}}
                    )
                    db.cameras.update_many(
                        {"stores": store_name}, {"$pull": {"stores": store_name}}
                    )
                    db.stores.delete_one({"name": store_name})
                    deleted.append(store_name)
                else:
                    not_found.append(store_name)

            logger.warning(f"Deleted stores: {deleted}, Not found: {not_found}")
            msg = (f"✅ Deleted stores: {', '.join(deleted)}. " if deleted else "") + (
                f"❌ Not found stores: {', '.join(not_found)}." if not_found else ""
            )
            return jsonify(msg=msg.strip()), 200
        except Exception as e:
            logger.critical(f"DELETE /stores failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @stores_bp.route("/stores/users", methods=["DELETE"])
    @jwt_required()
    def remove_users_from_store():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict) or data == {}:
                return jsonify(msg="❌ Body cannot be empty"), 400

            store_name = data.get("store_name", "").strip().upper()
            user_email = data.get("user_email")
            user_emails = data.get("user_emails")

            if not store_name:
                return jsonify(msg="❌ 'store_name' is required"), 400
            if user_email and user_emails:
                return (
                    jsonify(
                        msg="❌ Provide either 'user_email' or 'user_emails', not both"
                    ),
                    400,
                )

            if user_email:
                if not isinstance(user_email, str) or not user_email.strip():
                    return (
                        jsonify(msg="❌ 'user_email' must be a non-empty string"),
                        400,
                    )
                users_to_remove = [user_email.strip().upper()]
            elif user_emails:
                if not isinstance(user_emails, list) or not user_emails:
                    return (
                        jsonify(
                            msg="❌ 'user_emails' must be a non-empty list of strings"
                        ),
                        400,
                    )
                users_to_remove = [
                    e.strip().upper()
                    for e in user_emails
                    if isinstance(e, str) and e.strip()
                ]
                if not users_to_remove:
                    return (
                        jsonify(msg="❌ 'user_emails' list contains no valid emails"),
                        400,
                    )
            else:
                return (
                    jsonify(msg="❌ Either 'user_email' or 'user_emails' is required"),
                    400,
                )

            store = db.stores.find_one({"name": store_name})
            if not store:
                return jsonify(msg=f"❌ Store '{store_name}' not found"), 404

            removed_users, not_found_users, not_in_store = [], [], []
            for email in users_to_remove:
                user = db.users.find_one({"email": email})
                if not user:
                    not_found_users.append(email)
                    continue
                if email not in store.get("users", []):
                    not_in_store.append(email)
                    continue

                db.stores.update_one({"name": store_name}, {"$pull": {"users": email}})
                db.users.update_one({"email": email}, {"$pull": {"stores": store_name}})
                removed_users.append(email)

            msg_parts = []
            if removed_users:
                msg_parts.append(f"✅ Removed users: {', '.join(removed_users)}")
            if not_found_users:
                msg_parts.append(f"❌ Users not found: {', '.join(not_found_users)}")
            if not_in_store:
                msg_parts.append(
                    f"❌ Users not assigned to store: {', '.join(not_in_store)}"
                )

            logger.info(f"Removed users from store '{store_name}': {removed_users}")
            if not_found_users:
                logger.warning(f"Users not found: {not_found_users}")
            if not_in_store:
                logger.warning(f"Users not in store: {not_in_store}")

            return jsonify(msg=". ".join(msg_parts)), 200
        except Exception as e:
            logger.critical(f"DELETE /stores/users failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @stores_bp.route("/stores/users", methods=["POST"])
    @jwt_required()
    def add_users_to_store():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict) or data == {}:
                return jsonify(msg="❌ Body cannot be empty"), 400

            store_name = data.get("store_name", "").strip().upper()
            user_emails = data.get("user_email") or data.get("user_emails")

            if not store_name:
                return jsonify(msg="❌ 'store_name' is required"), 400
            if not user_emails:
                return jsonify(msg="❌ 'user_email' or 'user_emails' is required"), 400

            if isinstance(user_emails, str):
                user_emails = [user_emails.strip().upper()]
            elif isinstance(user_emails, list):
                user_emails = [
                    str(email).strip().upper()
                    for email in user_emails
                    if str(email).strip()
                ]
            else:
                return (
                    jsonify(msg="❌ 'user_email' must be a string or list of strings"),
                    400,
                )

            store = db.stores.find_one({"name": store_name})
            if not store:
                return jsonify(msg=f"❌ Store '{store_name}' not found"), 404

            added_users, already_in_store, missing_users = [], [], []
            current_users = store.get("users", [])

            for email in user_emails:
                if email in current_users:
                    already_in_store.append(email)
                    continue
                user = db.users.find_one({"email": email})
                if not user:
                    missing_users.append(email)
                    continue
                db.stores.update_one(
                    {"name": store_name}, {"$addToSet": {"users": email}}
                )
                db.users.update_one(
                    {"email": email}, {"$addToSet": {"stores": store_name}}
                )
                added_users.append(email)

            msg_parts = []
            if added_users:
                msg_parts.append(f"✅ Added users: {', '.join(added_users)}")
            if already_in_store:
                msg_parts.append(f"ℹ️ Already in store: {', '.join(already_in_store)}")
            if missing_users:
                msg_parts.append(
                    f"❌ Users not found: {', '.join(missing_users)}. Please create them first in the users endpoint."
                )

            logger.info(f"Added users to store '{store_name}': {added_users}")
            if already_in_store:
                logger.warning(f"Already in store: {already_in_store}")
            if missing_users:
                logger.warning(f"Users not found: {missing_users}")

            return jsonify(msg=". ".join(msg_parts)), 200
        except Exception as e:
            logger.critical(f"POST /stores/users failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @stores_bp.route("/stores/by_user", methods=["POST"])
    @jwt_required()
    def get_stores_by_user():
        try:
            data = request.get_json()
            if not data or "email" not in data:
                return jsonify(msg="❌ 'email' is required in body"), 400

            email = str(data["email"]).strip().upper()
            if not email_regex.match(email):
                return jsonify(msg="❌ Invalid email format"), 400

            stores = []
            for doc in db.stores.find({"users": email}):
                doc.pop("_id", None)
                ordered = OrderedDict()
                ordered["name"] = doc.get("name", "")
                ordered["clientID"] = doc.get("clientID", "")
                ordered["address"] = doc.get("address", "")
                ordered["users"] = doc.get("users", [])
                ordered["open_time"] = doc.get("open_time", "00:00")
                ordered["close_time"] = doc.get("close_time", "23:59")

                converted_cameras = []
                for cam in doc.get("cameras", []):
                    if isinstance(cam, dict):
                        cam = cam.copy()
                        if "_id" in cam:
                            cam["_id"] = str(cam["_id"])
                        if "name" not in cam:
                            cam["name"] = ""
                        converted_cameras.append(cam)
                    else:
                        converted_cameras.append(cam)

                ordered["cameras"] = converted_cameras
                stores.append(ordered)

            logger.info(f"Returned stores for user {email} ({len(stores)} found)")
            return Response(json.dumps({"stores": stores}), mimetype="application/json")
        except Exception as e:
            logger.critical(f"POST /stores/by_user failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500
