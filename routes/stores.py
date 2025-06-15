from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from collections import OrderedDict
import re
import json

stores_bp = Blueprint("stores", __name__)

# Regex for validating email formats (uppercase-safe)
email_regex = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$")

def init_store_routes(db):
    # -----------------------------------------
    # 🔍 GET /stores — Return all stores
    # -----------------------------------------
    """
    Returns a list of all store entries.

    ✅ Requires:
        - A valid access token

    🔐 Example:
        curl -k -X GET https://116.203.203.86/stores \
        -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc0OTg5MTU0MCwianRpIjoiMTUzNGJiYWEtNGU4Mi00ZDM0LTk4ODQtYmE1NWYyMWY0MDE4IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IkFkbWluSFMiLCJuYmYiOjE3NDk4OTE1NDAsImNzcmYiOiI5OGEzNThiMi0yODkyLTQ3ZjAtYjJhNy0yNmE0YmVhMTljOTkiLCJleHAiOjE3NDk4OTE2MDB9.QI7wmHaBTBzNPW30vKJYboFjCsw6c1cMhBXhtoGvOCs"
    """
    @stores_bp.route("/stores", methods=["GET"])
    @jwt_required()
    def get_stores():
        stores = []
        for doc in db.stores.find({}, {"_id": 0}):
            ordered = OrderedDict()
            ordered["name"] = doc.get("name", "")
            ordered["clientID"] = doc.get("clientID", "")
            ordered["address"] = doc.get("address", "")
            ordered["users"] = doc.get("users", [])

            converted_cameras = []
            for cam in doc.get("cameras", []):
                if isinstance(cam, dict):
                    cam = cam.copy()
                    if "_id" in cam:
                        cam["_id"] = str(cam["_id"])
                    if "name" not in cam:
                        cam["name"] = ""  # fallback for older entries
                    converted_cameras.append(cam)
                else:
                    converted_cameras.append(cam)

            ordered["cameras"] = converted_cameras
            stores.append(ordered)

        return Response(json.dumps({"stores": stores}), mimetype="application/json")



    # -----------------------------------------
    # ➕ POST /stores — Create a new store
    # -----------------------------------------
    """
    Creates a new store with required and optional fields.
    Auto-initializes 'cameras' as an empty list.

    ✅ Requires:
        - Access token
        - JSON body with at least 'name'

    🧪 Example input:
        {
            "name": "My Store",
            "clientID": "client-x",
            "address": "ZURICH",
            "users": ["a@x.ch", "b@y.com"]
        }

    ❌ Rejected if:
        - 'name' missing or duplicate
        - 'users' is not a list
        - Any email is invalid
        - 'cameras' is included manually

    ℹ️ Behavior:
        - Only existing users in the users collection will be added to the store.
        - Non-existing users will be ignored and listed in the response message.
        - Users that exist will have this store name added to their 'stores' list.

    ✅ Success response includes:
        {
            "msg": "✅ Store created. Non-existing users ignored: B@Y.COM. Please create them first in the users endpoint.",
            "store": { ... }
        }
    """

    @stores_bp.route("/stores", methods=["POST"])
    @jwt_required()
    def create_store():
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
            "users": clean_users,  # only existing users
            "cameras": []
        }

        insert_result = db.stores.insert_one(store)
        new_store = db.stores.find_one({"_id": insert_result.inserted_id}, {"_id": 0})

        # Sync store to users who exist
        for user_email in clean_users:
            db.users.update_one(
                {"email": user_email},
                {"$addToSet": {"stores": name}}
            )

        ordered_store = OrderedDict()
        ordered_store["name"] = new_store.get("name", "")
        ordered_store["clientID"] = new_store.get("clientID", "")
        ordered_store["address"] = new_store.get("address", "")
        ordered_store["users"] = new_store.get("users", [])
        ordered_store["cameras"] = new_store.get("cameras", [])

        msg = "✅ Store created."
        if missing_users:
            msg += f" Non-existing users ignored: {', '.join(missing_users)}. Please create them first in the users endpoint."

        response_data = OrderedDict()
        response_data["msg"] = msg
        response_data["store"] = ordered_store

        return Response(json.dumps(response_data), mimetype="application/json"), 201




    # -----------------------------------------
    # 🔄 PUT /stores — Update existing store
    # -----------------------------------------
    """
    Updates existing store fields except 'users' (which require dedicated endpoints).

    ✅ Requires:
        - Access token
        - JSON body with:
            - Mandatory: "name" (store name to identify store, case-insensitive)
            - Optional: fields to update (e.g. clientID, address, cameras)
            Fields will be converted to uppercase automatically if string.

    ❌ Rejected if:
        - Body is empty or not JSON
        - "name" missing or empty
        - Store with given name does not exist
        - Attempt to update "users" field
        - No valid fields to update provided

    🧪 Example request body:
        {
            "name": "STORE A",
            "clientID": "NEWCLIENTID",
            "address": "NEW ADDRESS",
            "new_name": "STORE B"    # Optional: to rename the store
        }

    ⚠️ Attempt to update users field:
        {
            "name": "STORE A",
            "users": ["newuser@example.com"]
        }
        => returns error: "❌ Field 'users' cannot be updated here. Use dedicated endpoints for users."

    🔐 Example curl (replace <TOKEN>):
        curl -k -X PUT https://your-url/stores \
        -H "Authorization: Bearer <TOKEN>" \
        -H "Content-Type: application/json" \
        -d '{"name": "STORE A", "new_name": "STORE B", "address": "ZURICH"}'

    ✅ Successful response:
        {
            "msg": "✅ Store 'STORE A' updated",
            "store": {
                "name": "STORE B",
                "clientID": "NEWCLIENTID",
                "address": "ZURICH",
                "users": [...],
                "cameras": [...]
            }
        }

    ℹ️ Additional behavior:
        - If "new_name" is provided and the store name changes,
        the function will sync the updated store name in all user documents
        who have this store in their "stores" list, replacing the old name with the new.
    """

    @stores_bp.route("/stores", methods=["PUT"])
    @jwt_required()
    def update_store():
        data = request.get_json()

        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        current_name = data.get("name") or data.get("current_name") or data.get("old_name")
        if not current_name or not isinstance(current_name, str):
            return jsonify(msg="❌ 'name' or 'current_name' of the store to update is required"), 400
        current_name = current_name.strip().upper()

        existing_store = db.stores.find_one({"name": current_name})
        if not existing_store:
            return jsonify(msg=f"❌ Store with name '{current_name}' not found"), 404

        new_name = data.get("new_name")
        if new_name:
            if not isinstance(new_name, str) or not new_name.strip():
                return jsonify(msg="❌ 'new_name' must be a non-empty string"), 400
            new_name = new_name.strip().upper()
            if new_name != current_name and db.stores.find_one({"name": new_name}):
                return jsonify(msg=f"❌ Store with name '{new_name}' already exists"), 409
        else:
            new_name = current_name

        disallowed_fields = {"users"}
        allowed_keys = set(existing_store.keys()) - {"_id", "users", "name"}

        update_fields = {}
        changes_made = False

        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in {"name", "current_name", "old_name", "new_name"}:
                continue
            if key_lower in disallowed_fields:
                return jsonify(msg=f"❌ Field '{key}' cannot be updated here. Use dedicated endpoints for users."), 400
            if key_lower not in allowed_keys:
                return jsonify(msg=f"❌ Field '{key}' is not allowed to be updated"), 400

            if isinstance(value, str):
                new_val = value.strip().upper()
            else:
                new_val = value

            if existing_store.get(key_lower) == new_val:
                continue

            update_fields[key_lower] = new_val
            changes_made = True

        if new_name != current_name:
            update_fields["name"] = new_name
            changes_made = True

        if not changes_made:
            return jsonify(msg="ℹ️ No changes detected to update"), 200

        db.stores.update_one({"name": current_name}, {"$set": update_fields})

        # If store name changed, update users' store lists
        if new_name != current_name:
            users = existing_store.get("users", [])
            for user_email in users:
                # Remove old store name
                db.users.update_one(
                    {"email": user_email},
                    {"$pull": {"stores": current_name}}
                )
                # Add new store name (avoid duplicates)
                db.users.update_one(
                    {"email": user_email},
                    {"$addToSet": {"stores": new_name}}
                )

        updated_store = db.stores.find_one({"name": new_name}, {"_id": 0})

        ordered_store = OrderedDict()
        ordered_store["name"] = updated_store.get("name", "")
        ordered_store["clientID"] = updated_store.get("clientID", "")
        ordered_store["address"] = updated_store.get("address", "")
        ordered_store["users"] = updated_store.get("users", [])
        ordered_store["cameras"] = updated_store.get("cameras", [])

        response_data = OrderedDict()
        response_data["msg"] = f"✅ Store '{current_name}' updated"
        response_data["store"] = ordered_store

        return Response(json.dumps(response_data), mimetype="application/json"), 200




    """
    🔴 DELETE /stores — Delete a store by name

    ✅ Requires:
        - Access token
        - JSON body with:
            - "name" (store name to delete, case-insensitive)

    ❌ Rejected if:
        - Body empty or invalid JSON
        - "name" missing or empty
        - Store with given name does not exist

    🧪 Example request body:
        {
            "name": "STORE A"
        }

    🔐 Example curl (replace <TOKEN>):
        curl -k -X DELETE https://your-url/stores \
        -H "Authorization: Bearer <TOKEN>" \
        -H "Content-Type: application/json" \
        -d '{"name": "STORE A"}'

    ✅ Successful response:
        {
            "msg": "✅ Store 'STORE A' deleted"
        }
    """

    @stores_bp.route("/stores", methods=["DELETE"])
    @jwt_required()
    def delete_store():
        data = request.get_json()

        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        force = data.get("force", False)
        if force is not True:
            return jsonify(msg="❌ You must confirm deletion with 'force': true"), 400

        names = data.get("name")
        if not names:
            return jsonify(msg="❌ 'name' field is required"), 400

        # Normalize input to list of uppercase store names
        if isinstance(names, str):
            store_names = [names.strip().upper()]
        elif isinstance(names, list):
            store_names = [str(n).strip().upper() for n in names if str(n).strip()]
            if not store_names:
                return jsonify(msg="❌ 'name' list is empty"), 400
        else:
            return jsonify(msg="❌ 'name' must be a string or list of strings"), 400

        deleted = []
        not_found = []

        for store_name in store_names:
            existing = db.stores.find_one({"name": store_name})
            if existing:
                db.stores.delete_one({"name": store_name})
                deleted.append(store_name)
            else:
                not_found.append(store_name)

        response_msg = ""
        if deleted:
            response_msg += f"✅ Deleted stores: {', '.join(deleted)}. "
        if not_found:
            response_msg += f"❌ Not found stores: {', '.join(not_found)}."

        return jsonify(msg=response_msg.strip()), 200
        
        
    """
    🔴 DELETE /stores/users — Remove one or more users from a store and sync user store lists

    ✅ Requires:
        - Access token
        - JSON body with:
            - "store_name": string (store name, case-insensitive)
            - "user_email": string (single user email to remove)
            - OR "user_emails": list of strings (multiple user emails to remove)

    ❌ Errors:
        - Missing required fields
        - Store not found
        - User(s) not found
        - User(s) not assigned to the given store

    🧪 Example request body (single user):
        {
            "store_name": "MY STORE",
            "user_email": "USER@EXAMPLE.COM"
        }

    🧪 Example request body (multiple users):
        {
            "store_name": "MY STORE",
            "user_emails": ["USER1@EXAMPLE.COM", "USER2@EXAMPLE.COM"]
        }

    🔐 Example curl (replace <TOKEN>):
        curl -k -X DELETE https://your-url/stores/users \
        -H "Authorization: Bearer <TOKEN>" \
        -H "Content-Type: application/json" \
        -d '{"store_name": "MY STORE", "user_emails": ["USER@EXAMPLE.COM", "OTHER@EXAMPLE.COM"]}'

    ✅ Success response:
        {
            "msg": "✅ Removed users: USER@EXAMPLE.COM, OTHER@EXAMPLE.COM. ❌ Users not found: MISSING@EXAMPLE.COM. ❌ Users not assigned to store: NOTINSTORE@EXAMPLE.COM"
        }
"""


    @stores_bp.route("/stores/users", methods=["DELETE"])
    @jwt_required()
    def remove_users_from_store():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        store_name = data.get("store_name", "").strip().upper()
        user_email = data.get("user_email")
        user_emails = data.get("user_emails")

        if not store_name:
            return jsonify(msg="❌ 'store_name' is required"), 400

        # Determine user list from user_email or user_emails keys
        if user_email and user_emails:
            return jsonify(msg="❌ Provide either 'user_email' or 'user_emails', not both"), 400

        if user_email:
            # Single user, normalize to list
            if not isinstance(user_email, str) or not user_email.strip():
                return jsonify(msg="❌ 'user_email' must be a non-empty string"), 400
            users_to_remove = [user_email.strip().upper()]
        elif user_emails:
            # Multiple users
            if not isinstance(user_emails, list) or not user_emails:
                return jsonify(msg="❌ 'user_emails' must be a non-empty list of strings"), 400
            users_to_remove = []
            for email in user_emails:
                if isinstance(email, str) and email.strip():
                    users_to_remove.append(email.strip().upper())
            if not users_to_remove:
                return jsonify(msg="❌ 'user_emails' list contains no valid emails"), 400
        else:
            return jsonify(msg="❌ Either 'user_email' or 'user_emails' is required"), 400

        # Find store
        store = db.stores.find_one({"name": store_name})
        if not store:
            return jsonify(msg=f"❌ Store '{store_name}' not found"), 404

        removed_users = []
        not_found_users = []
        not_in_store = []

        for user_email in users_to_remove:
            user = db.users.find_one({"email": user_email})
            if not user:
                not_found_users.append(user_email)
                continue
            if user_email not in store.get("users", []):
                not_in_store.append(user_email)
                continue

            # Remove user from store's users list
            db.stores.update_one({"name": store_name}, {"$pull": {"users": user_email}})

            # Remove store from user's stores list
            db.users.update_one({"email": user_email}, {"$pull": {"stores": store_name}})

            removed_users.append(user_email)

        msg_parts = []
        if removed_users:
            msg_parts.append(f"✅ Removed users: {', '.join(removed_users)}")
        if not_found_users:
            msg_parts.append(f"❌ Users not found: {', '.join(not_found_users)}")
        if not_in_store:
            msg_parts.append(f"❌ Users not assigned to store: {', '.join(not_in_store)}")

        return jsonify(msg=". ".join(msg_parts)), 200

        
    
    
    
    """
    ➕ POST /stores/users — Add one or more users to a store and sync user store lists

    ✅ Requires:
        - Access token
        - JSON body with:
            - "store_name": string (store name, case-insensitive)
            - "user_email" or "user_emails": string or list of strings (emails to add)

    ❌ Errors:
        - Missing required fields
        - Store not found
        - Invalid 'user_email' type (not string or list)

    ℹ️ Behavior:
        - Skips users already assigned to the store
        - Adds only users existing in the users collection
        - Syncs store list in each added user's record
        - Returns messages about added, skipped, and missing users

    🧪 Example request body (single user):
        {
            "store_name": "MY STORE",
            "user_email": "USER@EXAMPLE.COM"
        }

    🧪 Example request body (multiple users):
        {
            "store_name": "MY STORE",
            "user_emails": ["USER@EXAMPLE.COM", "NEWUSER@EXAMPLE.COM"]
        }

    🔐 Example curl (replace <TOKEN>):
        curl -k -X POST https://your-url/stores/users \
        -H "Authorization: Bearer <TOKEN>" \
        -H "Content-Type: application/json" \
        -d '{"store_name": "MY STORE", "user_emails": ["USER@EXAMPLE.COM", "NEWUSER@EXAMPLE.COM"]}'

    ✅ Success response example:
        {
            "msg": "✅ Added users: USER@EXAMPLE.COM. ℹ️ Already in store: EXISTING@EXAMPLE.COM. ❌ Users not found: NEWUSER@EXAMPLE.COM. Please create them first in the users endpoint."
        }
    """

    
    
    @stores_bp.route("/stores/users", methods=["POST"])
    @jwt_required()
    def add_users_to_store():
        data = request.get_json()
        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        store_name = data.get("store_name", "").strip().upper()
        user_emails = data.get("user_email") or data.get("user_emails")

        if not store_name:
            return jsonify(msg="❌ 'store_name' is required"), 400
        if not user_emails:
            return jsonify(msg="❌ 'user_email' or 'user_emails' is required"), 400

        # Normalize to list
        if isinstance(user_emails, str):
            user_emails = [user_emails.strip().upper()]
        elif isinstance(user_emails, list):
            user_emails = [str(email).strip().upper() for email in user_emails if str(email).strip()]
        else:
            return jsonify(msg="❌ 'user_email' must be a string or list of strings"), 400

        # Find store
        store = db.stores.find_one({"name": store_name})
        if not store:
            return jsonify(msg=f"❌ Store '{store_name}' not found"), 404

        already_in_store = []
        missing_users = []
        added_users = []
        not_in_store = []

        current_users = store.get("users", [])

        for email in user_emails:
            if email in current_users:
                already_in_store.append(email)
                continue

            user = db.users.find_one({"email": email})
            if not user:
                missing_users.append(email)
                continue

            # Add user to store's users list
            db.stores.update_one({"name": store_name}, {"$addToSet": {"users": email}})
            # Add store to user's stores list
            db.users.update_one({"email": email}, {"$addToSet": {"stores": store_name}})

            added_users.append(email)

        msg_parts = []
        if added_users:
            msg_parts.append(f"✅ Added users: {', '.join(added_users)}")
        if already_in_store:
            msg_parts.append(f"ℹ️ Already in store: {', '.join(already_in_store)}")
        if missing_users:
            msg_parts.append(f"❌ Users not found: {', '.join(missing_users)}. Please create them first in the users endpoint.")

        return jsonify(msg=". ".join(msg_parts)), 200

    
    
    
