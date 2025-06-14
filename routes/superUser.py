from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from collections import OrderedDict
import re
import json

super_user = Blueprint('super_user', __name__)


# Email regex uppercase-safe + German letters äöüßÄÖÜ allowed in local part and domain
email_regex = re.compile(
    r"^[A-Z0-9._%+\-äöüßÄÖÜ]+@[A-Z0-9.\-äöüßÄÖÜ]+\.[A-Z]{2,}$",
    re.IGNORECASE
)

# Password regex: min 8 chars, at least 1 uppercase and 1 digit
password_regex = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")

def init_super_user_routes(db):
    #hard rest user password with giving the old password
    @super_user_bp.route("/super_user/reset_password", methods=["PUT"])
    @jwt_required()
    def rest_user_password():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400
        super_password = data.get("super_password", "").strip()
        if not super_password:
            return (msg="❌ 'super_password' is required to execute this request"), 400
        
        
        