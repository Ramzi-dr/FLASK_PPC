from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from pytz import timezone
from logger import logger
import threading
from notify import notify_HS
import random
import string
import asyncio

user_login_bp = Blueprint("user_login", __name__)
tz_ch = timezone("Europe/Zurich")


def init_user_login_routes(db):
    @user_login_bp.route("/user_login", methods=["POST"])
    def user_login():
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify(msg="❌ Body cannot be empty"), 400

            email = data.get("email", "").strip().upper()
            password = data.get("password", "")

            if not email or not password:
                return jsonify(msg="❌ 'email' and 'password' required"), 400

            user = db.users.find_one({"email": email})
            if not user:
                logger.warning(f"USER_LOGIN failed: no user {email}")
                return jsonify(msg="❌ Invalid credentials"), 401

            if not check_password_hash(user["password"], password):
                logger.warning(f"USER_LOGIN failed: wrong password for {email}")
                return jsonify(msg="❌ Invalid credentials"), 401

            pincode = "".join(random.choices(string.digits, k=6))
            created_at = datetime.now(tz_ch)

            db.pincodes.delete_many({"email": email})
            db.pincodes.insert_one(
                {
                    "email": email,
                    "pincode": pincode,
                    "created_at": created_at.isoformat(),
                }
            )

            msg = f"🔐 Your login pincode is:\n\n<b>{pincode}</b>\n\n⏱️ Valid 5 minutes only."
            logger.info(f"✅ Pincode sent to {email}")

            try:

                threading.Thread(
                    target=asyncio.run, args=(notify_HS(msg, logger, email),)
                ).start()

            except Exception as e:
                logger.warning(f"⚠️ Notify error: {e}")

            return jsonify(msg="✅ Pincode sent via email"), 200

        except Exception as e:
            logger.critical(f"/user_login error: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @user_login_bp.route("/verify_pincode", methods=["POST"])
    def verify_pincode():
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify(msg="❌ Body cannot be empty"), 400

            email = data.get("email", "").strip().upper()
            pincode = data.get("pincode", "").strip()

            if not email or not pincode:
                return jsonify(msg="❌ 'email' and 'pincode' required"), 400

            doc = db.pincodes.find_one({"email": email, "pincode": pincode})
            if not doc:
                logger.warning(f"PINCODE fail: no match for {email}")
                return jsonify(msg="❌ Invalid or expired pincode"), 401

            now = datetime.now(tz_ch)
            created_at = doc["created_at"]

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            if created_at.tzinfo is None:
                created_at = tz_ch.localize(created_at)

            if now - created_at > timedelta(minutes=5):
                db.pincodes.delete_many({"email": email})
                logger.warning(f"PINCODE expired for {email}")
                return jsonify(msg="❌ Pincode expired"), 401

            db.pincodes.delete_many({"email": email})
            access_token = create_access_token(
                identity=email, additional_claims={"role": "user"}
            )
            refresh_token = create_refresh_token(
                identity=email, additional_claims={"role": "user"}
            )

            access_expiry = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
            refresh_expiry = current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]

            logger.info(f"✅ Pincode OK: tokens issued for {email}")

            return (
                jsonify(
                    msg="✅ Pincode verified",
                    access_token=access_token,
                    refresh_token=refresh_token,
                    access_expires_in=int(access_expiry.total_seconds()),
                    refresh_expires_in=int(refresh_expiry.total_seconds()),
                ),
                200,
            )

        except Exception as e:
            logger.critical(f"/verify_pincode error: {e}")
            return jsonify(msg="❌ Internal server error"), 500
