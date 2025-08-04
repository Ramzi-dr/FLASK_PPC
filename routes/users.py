from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt
from collections import OrderedDict
import re
import json
from werkzeug.security import generate_password_hash, check_password_hash
from logger import logger

users_bp = Blueprint("users", __name__)

email_regex = re.compile(
    r"^[A-Z0-9._%+\-äöüßÄÖÜ]+@[A-Z0-9.\-äöüßÄÖÜ]+\.[A-Z]{2,}$", re.IGNORECASE
)

password_regex = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


def init_user_routes(db):
    @users_bp.route("/users", methods=["POST"])
    @jwt_required()
    def create_user():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                logger.warning("POST /users: Empty or invalid body")
                return jsonify(msg="❌ Body cannot be empty"), 400

            email = data.get("email", "").strip()
            password = data.get("password", "")

            if not email:
                return jsonify(msg="❌ 'email' is required"), 400
            if not password:
                return jsonify(msg="❌ 'password' is required"), 400

            if not email_regex.match(email):
                return jsonify(msg="❌ Invalid email format"), 400

            if not password_regex.match(password):
                return (
                    jsonify(
                        msg="❌ Password must be at least 8 chars, with 1 uppercase and 1 number"
                    ),
                    400,
                )

            email_upper = email.upper()

            if db.users.find_one({"email": email_upper}):
                logger.warning(f"POST /users: Duplicate user {email_upper}")
                return (
                    jsonify(msg=f"❌ User with email '{email_upper}' already exists"),
                    409,
                )

            def clean_field(key):
                val = data.get(key, "")
                if not isinstance(val, str):
                    return ""
                val = val.strip().upper()
                if len(val) > 20:
                    raise ValueError(f"Field '{key}' too long (max 20 chars)")
                return val

            clientID = clean_field("clientID")
            name = clean_field("name")
            tel = clean_field("tel")
            address = clean_field("address")

            if tel and (not tel.isdigit() or len(tel) < 8):
                return (
                    jsonify(msg="❌ 'tel' must be digits and at least 8 characters"),
                    400,
                )

            hashed_pw = generate_password_hash(password)

            user_doc = {
                "email": email_upper,
                "password": hashed_pw,
                "clientID": clientID,
                "name": name,
                "tel": tel,
                "address": address,
                "stores": [],
            }

            db.users.insert_one(user_doc)
            logger.info(f"User created: {email_upper}")

            ordered_user = OrderedDict(
                {
                    "email": email_upper,
                    "clientID": clientID,
                    "name": name,
                    "tel": tel,
                    "address": address,
                    "stores": [],
                }
            )

            return (
                Response(
                    json.dumps({"msg": "✅ User created", "user": ordered_user}),
                    mimetype="application/json",
                ),
                201,
            )

        except Exception as e:
            logger.critical(f"POST /users error: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @users_bp.route("/users", methods=["GET"])
    @jwt_required()
    def get_users():
        # claims = get_jwt()
        # if claims.get("role") != "admin":
        #     return jsonify(msg="❌ Admins only"), 403
        try:
            users = []
            for doc in db.users.find({}, {"_id": 0, "password": 0}):
                users.append(
                    OrderedDict(
                        {
                            "email": doc.get("email", ""),
                            "clientID": doc.get("clientID", ""),
                            "name": doc.get("name", ""),
                            "tel": doc.get("tel", ""),
                            "address": doc.get("address", ""),
                            "stores": doc.get("stores", []),
                        }
                    )
                )
            return jsonify(users=users)
        except Exception as e:
            logger.critical(f"GET /users error: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @users_bp.route("/users", methods=["PUT"])
    @jwt_required()
    def update_user():
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify(msg="❌ Body cannot be empty"), 400

            email = data.get("email", "").strip().upper()
            if not email:
                return jsonify(msg="❌ 'email' is required to identify the user"), 400

            user = db.users.find_one({"email": email})
            if not user:
                return jsonify(msg=f"❌ User '{email}' not found"), 404

            disallowed = {"stores"}
            update_fields = {}

            for key, value in data.items():
                k = key.lower()
                if k in disallowed or k == "email":
                    continue
                if isinstance(value, str) and len(value) > 20:
                    return jsonify(msg=f"❌ Field '{k}' too long (max 20 chars)"), 400
                if k == "tel" and (not str(value).isdigit() or len(str(value)) < 8):
                    return (
                        jsonify(
                            msg="❌ 'tel' must be digits and at least 8 characters"
                        ),
                        400,
                    )
                if k == "password":
                    old_pw = data.get("old_password")
                    if not old_pw or not check_password_hash(
                        user.get("password", ""), old_pw
                    ):
                        return jsonify(msg="❌ Invalid or missing 'old_password'"), 400
                    if not password_regex.match(value):
                        return (
                            jsonify(
                                msg="❌ Password must be at least 8 chars, with 1 uppercase and 1 number"
                            ),
                            400,
                        )
                    update_fields["password"] = generate_password_hash(value)
                elif k == "new_email":
                    new_email = value.strip().upper()
                    if not email_regex.match(new_email):
                        return jsonify(msg="❌ Invalid new email format"), 400
                    if db.users.find_one({"email": new_email}):
                        return (
                            jsonify(msg=f"❌ Email '{new_email}' already exists"),
                            409,
                        )
                    update_fields["email"] = new_email
                    db.stores.update_many(
                        {"users": email}, {"$set": {"users.$": new_email}}
                    )
                else:
                    update_fields[k] = (
                        value.strip().upper() if isinstance(value, str) else value
                    )

            if not update_fields:
                return jsonify(msg="ℹ️ No changes provided"), 200

            db.users.update_one({"email": email}, {"$set": update_fields})
            updated_user = db.users.find_one(
                {"email": update_fields.get("email", email)}, {"_id": 0, "password": 0}
            )
            logger.info(f"User updated: {email}")

            return jsonify(msg="✅ User updated", user=updated_user), 200
        except Exception as e:
            logger.critical(f"PUT /users error: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @users_bp.route("/users", methods=["DELETE"])
    @jwt_required()
    def delete_users():
        # claims = get_jwt()
        # if claims.get("role") != "admin":
        #     return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify(msg="❌ Body cannot be empty"), 400

            raw_emails = data.get("emails") or data.get("email")
            if isinstance(raw_emails, str):
                emails = [raw_emails.strip().upper()]
            elif isinstance(raw_emails, list):
                emails = [e.strip().upper() for e in raw_emails if isinstance(e, str)]
            else:
                return jsonify(msg="❌ Provide 'email' or 'emails' field"), 400

            if not emails:
                return jsonify(msg="❌ No valid emails provided"), 400

            if not data.get("force"):
                return (
                    jsonify(msg="❌ You must confirm deletion with 'force': true"),
                    400,
                )

            deleted = []
            not_found = []

            for email in emails:
                if db.users.find_one({"email": email}):
                    db.stores.update_many({"users": email}, {"$pull": {"users": email}})
                    db.users.delete_one({"email": email})
                    deleted.append(email)
                else:
                    not_found.append(email)

            logger.info(f"Deleted users: {deleted}, Not found: {not_found}")
            msg = ""
            if deleted:
                msg += f"✅ Deleted: {', '.join(deleted)}. "
            if not_found:
                msg += f"❌ Not found: {', '.join(not_found)}"
            return jsonify(msg=msg.strip()), 200
        except Exception as e:
            logger.critical(f"DELETE /users error: {e}")
            return jsonify(msg="❌ Internal server error"), 500
