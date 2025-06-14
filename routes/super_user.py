from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from collections import OrderedDict
import re
import json
import bcrypt

super_user_bp = Blueprint('super_user', __name__)

# Email regex (uppercase-safe)
email_regex = re.compile(
    r"^[A-Z0-9._%+\-äöüßÄÖÜ]+@[A-Z0-9.\-äöüßÄÖÜ]+\.[A-Z]{2,}$",
    re.IGNORECASE
)

# Password regex: min 8 chars, at least 1 uppercase and 1 digit
password_regex = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")

def init_super_user_routes(db):
    """
    🔐 PUT /super_user/reset_password — Hard reset user password with super password

    ✅ Requires:
        - JWT access token
        - JSON body with:
            - "super_password": string (required, matches bcrypt-hashed SUPER_PASSWORD in env collection)
            - "email": string (user email to reset password, must be valid email format)
            - "new_password": string (new password, must meet complexity requirements)
            - "force": boolean (must be true to confirm reset)

    ❌ Errors:
        - Missing required fields
        - Invalid super_password
        - Invalid email format
        - User not found
        - "force" not true
        - Password does not meet complexity requirements

    🧪 Example request:
        {
            "super_password": "SuperSecretPlainText",
            "email": "user@example.com",
            "new_password": "NewPass123",
            "force": true
        }

    🔐 Example curl:
        curl -k -X PUT https://your-url/super_user/reset_password \
        -H "Authorization: Bearer <TOKEN>" \
        -H "Content-Type: application/json" \
        -d '{"super_password": "SuperSecretPlainText", "email": "user@example.com", "new_password": "NewPass123", "force": true}'

    ✅ Success response:
        {
            "msg": "✅ Password for user USER@EXAMPLE.COM reset successfully"
        }
    """
    @super_user_bp.route("/super_user/reset_password", methods=["PUT"])
    @jwt_required()
    def reset_user_password():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        super_password_plain = data.get("super_password", "").strip()
        if not super_password_plain:
            return jsonify(msg="❌ 'super_password' is required"), 400

        email = data.get("email", "").strip()
        if not email:
            return jsonify(msg="❌ 'email' is required"), 400
        email_upper = email.upper()
        if not email_regex.match(email):
            return jsonify(msg="❌ Invalid email format"), 400

        new_password = data.get("new_password", "").strip()
        if not new_password:
            return jsonify(msg="❌ 'new_password' is required"), 400

        force = data.get("force", False)
        if force is not True:
            return jsonify(msg="❌ 'force' must be true to confirm reset"), 400

        # Get hashed super_password from env collection
        env_doc = db.env.find_one({"key": "SUPER_PASSWORD"})
        if not env_doc or "value" not in env_doc:
            return jsonify(msg="❌ Super password not configured"), 500

        hashed_super_password = env_doc["value"]

        # Verify super_password
        if not bcrypt.checkpw(super_password_plain.encode(), hashed_super_password.encode()):
            return jsonify(msg="❌ Invalid super_password"), 403

        # Check user existence
        user = db.users.find_one({"email": email_upper})
        if not user:
            return jsonify(msg=f"❌ User with email '{email_upper}' not found"), 404

        # Validate new_password complexity
        if not password_regex.match(new_password):
            return jsonify(msg="❌ Password must be at least 8 chars, with 1 uppercase and 1 number"), 400

        # Hash new password and update user
        hashed_new_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        db.users.update_one({"email": email_upper}, {"$set": {"password": hashed_new_pw}})

        return jsonify(msg=f"✅ Password for user {email_upper} reset successfully"), 200
