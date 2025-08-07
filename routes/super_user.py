""" super_user.py """

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
import re
import bcrypt
from logger import logger  # ✅ import logger

super_user_bp = Blueprint("super_user", __name__)

# Email regex (uppercase-safe)
email_regex = re.compile(
    r"^[A-Z0-9._%+\-äöüßÄÖÜ]+@[A-Z0-9.\-äöüßÄÖÜ]+\.[A-Z]{2,}$", re.IGNORECASE
)

# Password regex: min 8 chars, at least 1 uppercase and 1 digit
password_regex = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


def init_super_user_routes(db):
    """
    🔐 PUT /super_user/reset_password — Hard reset user password with super password
    (see original docstring for full detail)
    """

    @super_user_bp.route("/super_user/reset_password", methods=["PUT"])
    @jwt_required()
    def reset_user_password():
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(msg="❌ Admins only"), 403
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict) or data == {}:
                logger.warning("PUT /super_user/reset_password: Empty or invalid body")
                return jsonify(msg="❌ Body cannot be empty"), 400

            super_password_plain = data.get("super_password", "").strip()
            if not super_password_plain:
                return jsonify(msg="❌ 'super_password' is required"), 400

            email = data.get("email", "").strip()
            if not email:
                return jsonify(msg="❌ 'email' is required"), 400
            if not email_regex.match(email):
                return jsonify(msg="❌ Invalid email format"), 400
            email_upper = email.upper()

            new_password = data.get("new_password", "").strip()
            if not new_password:
                return jsonify(msg="❌ 'new_password' is required"), 400

            force = data.get("force", False)
            if force is not True:
                return jsonify(msg="❌ 'force' must be true to confirm reset"), 400

            # Get hashed super_password from env
            env_doc = db.env.find_one({"key": "SUPER_PASSWORD"})
            if not env_doc or "value" not in env_doc:
                logger.critical(
                    "PUT /super_user/reset_password: SUPER_PASSWORD not found in env"
                )
                return jsonify(msg="❌ Super password not configured"), 500

            hashed_super_password = env_doc["value"]

            if not bcrypt.checkpw(
                super_password_plain.encode(), hashed_super_password.encode()
            ):
                logger.warning("PUT /super_user/reset_password: Invalid super_password")
                return jsonify(msg="❌ Invalid super_password"), 403

            user = db.users.find_one({"email": email_upper})
            if not user:
                logger.warning(
                    f"PUT /super_user/reset_password: User {email_upper} not found"
                )
                return jsonify(msg=f"❌ User with email '{email_upper}' not found"), 404

            if not password_regex.match(new_password):
                return (
                    jsonify(
                        msg="❌ Password must be at least 8 chars, with 1 uppercase and 1 number"
                    ),
                    400,
                )

            hashed_new_pw = bcrypt.hashpw(
                new_password.encode(), bcrypt.gensalt()
            ).decode()

            db.users.update_one(
                {"email": email_upper}, {"$set": {"password": hashed_new_pw}}
            )
            logger.info(
                f"PUT /super_user/reset_password: Password reset for {email_upper}"
            )

            return (
                jsonify(msg=f"✅ Password for user {email_upper} reset successfully"),
                200,
            )
        except Exception as e:
            logger.critical(f"PUT /super_user/reset_password error: {e}")
            return jsonify(msg="❌ Internal server error"), 500
