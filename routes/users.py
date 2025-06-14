from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from collections import OrderedDict
import re
import json

users_bp = Blueprint("users", __name__)

# Email regex uppercase-safe + German letters äöüßÄÖÜ allowed in local part and domain
email_regex = re.compile(
    r"^[A-Z0-9._%+\-äöüßÄÖÜ]+@[A-Z0-9.\-äöüßÄÖÜ]+\.[A-Z]{2,}$",
    re.IGNORECASE
)

# Password regex: min 8 chars, at least 1 uppercase and 1 digit
password_regex = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")

def init_user_routes(db):
    """
    ➕ POST /users — Create new user

    ✅ Requires:
        - Access token
        - JSON body with required: email, password
        - Optional: clientID, name, tel, address (default empty strings)

    ❌ Errors:
        - Missing required fields
        - Invalid email or password format
        - User with email already exists

    🔐 Example:
    {
        "email": "user@example.com",
        "password": "Pass1234",
        "clientID": "CLIENT1",
        "name": "John Doe",
        "tel": "123456",
        "address": "Zurich"
    }

    ✅ Success response:
    {
        "msg": "✅ User created",
        "user": {
            "email": "USER@EXAMPLE.COM",
            "clientID": "CLIENT1",
            "name": "JOHN DOE",
            "tel": "123456",
            "address": "ZURICH",
            "stores": []
        }
    }
    """
    @users_bp.route("/users", methods=["POST"])
    @jwt_required()
    def create_user():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        # Required fields
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email:
            return jsonify(msg="❌ 'email' is required"), 400
        if not password:
            return jsonify(msg="❌ 'password' is required"), 400

        # Validate email format
        if not email_regex.match(email):
            return jsonify(msg="❌ Invalid email format"), 400

        # Validate password format
        if not password_regex.match(password):
            return jsonify(msg="❌ Password must be at least 8 chars, with 1 uppercase and 1 number"), 400

        # Normalize email to uppercase for storage and lookup
        email_upper = email.upper()

        # Check for existing user
        if db.users.find_one({"email": email_upper}):
            return jsonify(msg=f"❌ User with email '{email_upper}' already exists"), 409

        # Optional fields (uppercase except password)
        clientID = data.get("clientID", "").strip().upper()
        name = data.get("name", "").strip().upper()
        tel = data.get("tel", "").strip().upper()
        address = data.get("address", "").strip().upper()

        user_doc = {
            "email": email_upper,
            "password": password,  # Store as is (consider hashing in production)
            "clientID": clientID,
            "name": name,
            "tel": tel,
            "address": address,
            "stores": []
        }

        db.users.insert_one(user_doc)

        ordered_user = OrderedDict()
        ordered_user["email"] = user_doc["email"]
        ordered_user["clientID"] = user_doc["clientID"]
        ordered_user["name"] = user_doc["name"]
        ordered_user["tel"] = user_doc["tel"]
        ordered_user["address"] = user_doc["address"]
        ordered_user["stores"] = user_doc["stores"]

        response_data = OrderedDict()
        response_data["msg"] = "✅ User created"
        response_data["user"] = ordered_user

        return Response(json.dumps(response_data), mimetype="application/json"), 201

    @users_bp.route("/users", methods=["GET"])
    @jwt_required()
    def get_users():
        users = []
        for doc in db.users.find({}, {"_id": 0, "password": 0}):
            ordered = OrderedDict()
            ordered["email"] = doc.get("email", "")
            ordered["clientID"] = doc.get("clientID", "")
            ordered["name"] = doc.get("name", "")
            ordered["tel"] = doc.get("tel", "")
            ordered["address"] = doc.get("address", "")
            ordered["stores"] = doc.get("stores", [])
            users.append(ordered)
        response_data = {"users": users}
        return Response(json.dumps(response_data), mimetype="application/json")
        
    """
    🔄 PUT /users — Update existing user

    - Requires JWT access token
    - Request body must be JSON with:
        - "email" (string, required): current user email to identify the user (case-insensitive)
        - Optional fields to update (strings will be uppercased):
            - "clientID", "name", "tel", "address"
            - "password" (requires "old_password" to verify current password)
            - "new_email" (must be valid email format and unique)

    - Restrictions:
        - "stores" field cannot be updated here
        - Password update requires correct old_password
        - Email update requires unique and valid new_email

    - Additional behavior:
        - If "new_email" is changed, all stores where the old email exists in the "users" list will be updated to replace old email with new email, syncing user-store relationships.
        - (If user names are stored in stores, name sync logic can be added similarly.)

    - Example request to update name and address:
        {
            "email": "USER@EXAMPLE.COM",
            "name": "John Smith",
            "address": "New York"
        }

    - Example request to change password:
        {
            "email": "USER@EXAMPLE.COM",
            "password": "NewPass123",
            "old_password": "OldPass123"
        }

    - Example request to change email:
        {
            "email": "USER@EXAMPLE.COM",
            "new_email": "NEWUSER@EXAMPLE.COM"
        }

    - Success responses include updated user data with keys in fixed order.

    - Possible errors:
        - Missing "email"
        - User not found
        - Attempt to update disallowed fields ("stores")
        - Password update without old_password or incorrect old_password
        - Invalid new_email format or duplicate email
        - Password complexity rules violation
        - No valid update fields provided
    """

    
    @users_bp.route("/users", methods=["PUT"])
    @jwt_required()
    def update_user():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        email = data.get("email", "").strip()
        if not email:
            return jsonify(msg="❌ 'email' is required to identify the user"), 400
        email_upper = email.upper()

        existing_user = db.users.find_one({"email": email_upper})
        if not existing_user:
            return jsonify(msg=f"❌ User with email '{email_upper}' not found"), 404

        disallowed_fields = {"stores"}
        update_fields = {}
        password_update = False
        changes_made = False

        new_email_upper = None
        new_name_upper = None

        for key, value in data.items():
            key_lower = key.lower()
            if key_lower == "email":
                continue
            if key_lower in disallowed_fields:
                return jsonify(msg=f"❌ Field '{key}' cannot be updated here."), 400

            if key_lower == "password":
                old_pass = data.get("old_password")
                if not old_pass:
                    return jsonify(msg="❌ 'old_password' is required to update password"), 400
                if old_pass != existing_user.get("password"):
                    return jsonify(msg="❌ 'old_password' does not match"), 400
                if not password_regex.match(value):
                    return jsonify(msg="❌ Password must be at least 8 chars, with 1 uppercase and 1 number"), 400
                update_fields["password"] = value
                password_update = True
                changes_made = True
                continue

            if key_lower == "new_email":
                new_email = value.strip()
                if not email_regex.match(new_email):
                    return jsonify(msg="❌ Invalid new email format"), 400
                new_email_upper = new_email.upper()
                if new_email_upper != email_upper and db.users.find_one({"email": new_email_upper}):
                    return jsonify(msg=f"❌ User with email '{new_email_upper}' already exists"), 409
                if existing_user.get("email") != new_email_upper:
                    update_fields["email"] = new_email_upper
                    changes_made = True
                continue

            if key_lower == "name":
                new_name_upper = value.strip().upper()
                if existing_user.get("name") != new_name_upper:
                    update_fields["name"] = new_name_upper
                    changes_made = True
                continue

            # For other fields, uppercase strings except password handled above
            new_val = value.strip().upper() if isinstance(value, str) else value
            if existing_user.get(key_lower) != new_val:
                update_fields[key_lower] = new_val
                changes_made = True

        if not changes_made:
            return jsonify(msg="ℹ️ No changes detected"), 200

        # Update user document
        db.users.update_one({"email": email_upper}, {"$set": update_fields})

        # If email changed, update it in all stores' users lists
        if new_email_upper and new_email_upper != email_upper:
            db.stores.update_many(
                {"users": email_upper},
                {"$set": {"users.$": new_email_upper}}
            )

        # If name changed, sync user name in stores if stored there (if applicable)
        # (Assuming stores only keep user emails, not names, so skip)
        # If you keep names in stores, add sync code here

        updated_user = db.users.find_one({"email": update_fields.get("email", email_upper)}, {"_id": 0, "password": 0})

        ordered_user = OrderedDict()
        ordered_user["email"] = updated_user.get("email", "")
        ordered_user["clientID"] = updated_user.get("clientID", "")
        ordered_user["name"] = updated_user.get("name", "")
        ordered_user["tel"] = updated_user.get("tel", "")
        ordered_user["address"] = updated_user.get("address", "")
        ordered_user["stores"] = updated_user.get("stores", [])

        msg = "✅ User updated"
        if password_update:
            msg += " (password changed)"

        return Response(json.dumps({"msg": msg, "user": ordered_user}), mimetype="application/json"), 200
    
    """
    🔴 DELETE /users — Delete one or more users and sync removal from all stores

    ✅ Requires:
        - Access token
        - JSON body with:
            - "emails": list of user email strings to delete (case-insensitive)
            - "force": true (confirmation flag)

    ❌ Errors:
        - Missing or empty "emails" list
        - "force" not true
        - Any user email not found (reported in response, but deletion proceeds for others)

    🧪 Example request body (single user):
        {
            "emails": ["USER@EXAMPLE.COM"],
            "force": true
        }

    🧪 Example request body (multiple users):
        {
            "emails": ["USER1@EXAMPLE.COM", "USER2@EXAMPLE.COM"],
            "force": true
        }

    🔐 Example curl (replace <TOKEN>):
        curl -k -X DELETE https://your-url/users \
        -H "Authorization: Bearer <TOKEN>" \
        -H "Content-Type: application/json" \
        -d '{"emails": ["USER@EXAMPLE.COM", "OTHER@EXAMPLE.COM"], "force": true}'

    ✅ Success response:
        {
            "msg": "✅ Deleted users: USER@EXAMPLE.COM, OTHER@EXAMPLE.COM. ❌ Not found: MISSING@EXAMPLE.COM"
        }
    """

    @users_bp.route("/users", methods=["DELETE"])
    @jwt_required()
    def delete_users():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        emails = data.get("emails")
        force = data.get("force", False)

        if not emails or not isinstance(emails, list):
            return jsonify(msg="❌ 'emails' must be a non-empty list of email strings"), 400
        if force is not True:
            return jsonify(msg="❌ You must confirm deletion with 'force': true"), 400

        normalized_emails = [email.strip().upper() for email in emails if isinstance(email, str) and email.strip()]
        if not normalized_emails:
            return jsonify(msg="❌ 'emails' list is empty or invalid"), 400

        deleted = []
        not_found = []

        for email in normalized_emails:
            user = db.users.find_one({"email": email})
            if not user:
                not_found.append(email)
                continue

            # Remove user from all stores
            db.stores.update_many(
                {"users": email},
                {"$pull": {"users": email}}
            )

            # Delete user
            db.users.delete_one({"email": email})
            deleted.append(email)

        msg_parts = []
        if deleted:
            msg_parts.append(f"✅ Deleted users: {', '.join(deleted)}")
        if not_found:
            msg_parts.append(f"❌ Not found: {', '.join(not_found)}")

        return jsonify(msg=". ".join(msg_parts)), 200

