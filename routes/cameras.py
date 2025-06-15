from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from collections import OrderedDict
import re
import json
from urllib.parse import urlparse
import bcrypt

cameras_bp = Blueprint("cameras", __name__)

# URL regex to validate URLs with port (supports http, https, ws, wss)
url_regex = re.compile(
    r"^(https?|wss?):\/\/"               # scheme
    r"(([A-Z0-9\-\.]+)|(\[[A-F0-9:]+\]))"  # domain or IPv6
    r":(\d+)"                           # port (mandatory)
    r"(\/.*)?$",                       # optional path
    re.IGNORECASE
)

def init_camera_routes(db):
    #get cameras
    @cameras_bp.route("/cameras", methods=["GET"])
    @jwt_required()
    def get_all_cameras():
        cameras = db.cameras.find({}, {"_id": 1, "url": 1, "stores": 1, "name": 1})
        result = []
        for cam in cameras:
            cam["_id"] = str(cam["_id"])  # Convert ObjectId to string for JSON
            result.append(cam)
        return jsonify(result)



        """
    The `create_camera()` function creates a new camera entry in the database. It accepts a JSON body with the following:

    - Required: `url`, `username`, `password`
    - Optional: `name`, `store`

    The `url` must include the protocol and port (e.g., `http://192.168.1.100:554`).
    If a `store` is provided, it checks that the store exists and appends the camera's info
    (`_id`, `url`, `name`) to the store's camera list.

    All `url`, `name`, and `store` values are uppercased for consistency.
    The password is stored as plain text for now but can be hashed if needed.

    Example with store:
    ```bash
    curl -X POST https://116.203.203.86/cameras
      -H "Authorization: Bearer <JWT_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{
            "url": "http://192.168.1.100:554",
            "username": "admin",
            "password": "pass123",
            "store": "MAIN STORE",
            "name": "Front Door Cam"
          }'
    ```

    Example without store:
    ```bash
    curl -X POST https://116.203.203.86/cameras
      -H "Authorization: Bearer <JWT_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{
            "url": "http://192.168.1.100:554",
            "username": "admin",
            "password": "pass123",
            "name": "Front Door Cam"
          }'
    ```
    """

    @cameras_bp.route("/cameras", methods=["POST"])
    @jwt_required()
    def create_camera():
        data = request.get_json()

        if not data or not isinstance(data, dict) or data == {}:
            return jsonify(msg="❌ Body cannot be empty"), 400

        url = data.get("url", "").strip()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        store_name = data.get("store", "").strip()
        name = data.get("name", "").strip()

        if not url:
            return jsonify(msg="❌ 'url' is required"), 400
        if not username:
            return jsonify(msg="❌ 'username' is required"), 400
        if not password:
            return jsonify(msg="❌ 'password' is required"), 400

        if not url_regex.match(url):
            return jsonify(msg="❌ 'url' must be a valid URL including port, e.g. http://192.168.1.100:554"), 400

        normalized_url = url.upper()
        normalized_store = store_name.upper() if store_name else None
        normalized_name = name.upper() if name else ""

        if db.cameras.find_one({"url": normalized_url}):
            return jsonify(msg=f"❌ Camera with URL '{normalized_url}' already exists"), 409

        stores_list = []
        if normalized_store:
            store_doc = db.stores.find_one({"name": normalized_store})
            if not store_doc:
                return jsonify(msg=f"❌ Store '{normalized_store}' not found. Create store before adding camera."), 404
            stores_list.append(normalized_store)

        camera_doc = {
            "url": normalized_url,
            "username": username,
            "password": password,
            "stores": stores_list,
            "name": normalized_name
        }

        insert_result = db.cameras.insert_one(camera_doc)
        camera_id = insert_result.inserted_id

        if normalized_store:
            db.stores.update_one(
                {"name": normalized_store},
                {"$addToSet": {
                    "cameras": {
                        "name": normalized_name,
                        "_id": camera_id,
                        "url": normalized_url
                    }
                }}
            )

        ordered_camera = OrderedDict()
        ordered_camera["_id"] = str(camera_id)
        ordered_camera["url"] = camera_doc["url"]
        ordered_camera["username"] = camera_doc["username"]
        ordered_camera["password"] = camera_doc["password"]
        ordered_camera["stores"] = camera_doc["stores"]
        ordered_camera["name"] = camera_doc["name"]

        return Response(
            json.dumps({"msg": "✅ Camera created", "camera": ordered_camera}),
            mimetype="application/json",
            status=201
        )

        
    """
    This endpoint updates a camera by its `url`. Use `"url"` when you're not changing the URL,
    or `"current_url"` and `"new_url"` if you're updating the URL. Only `name`, `username`, `password`,
    and `url` can be updated—any attempt to modify `stores` is blocked with a clear error.
    Passwords are hashed before saving. If the `url` or `name` is changed, associated stores are
    updated to reflect the new values. All fields except password and username are stored in uppercase.

    Example without changing URL:
    curl -X PUT https://116.203.203.86/cameras
      -H "Authorization: Bearer <JWT_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{
        "url": "http://192.168.1.100:554",
        "name": "Updated Camera Name",
        "username": "newAdminUser",
        "password": "newSecurePassword123"
      }'

    Example with URL change:
    curl -X PUT https://116.203.203.86/cameras
      -H "Authorization: Bearer <JWT_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{
        "current_url": "http://192.168.1.100:554",
        "new_url": "http://192.168.1.100:556",
        "name": "Updated Camera Name",
        "username": "newAdminUser",
        "password": "newSecurePassword123"
      }'
    """
    @cameras_bp.route("/cameras", methods=["PUT"])
    @jwt_required()
    def update_camera():
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify(msg="❌ Body cannot be empty"), 400

        if "stores" in data:
            return jsonify(msg="❌ Camera stores list can be edited in camera/stores endpoint"), 400

        # Determine which field to identify the camera by
        camera_url = data.get("current_url") or data.get("url")
        if not camera_url:
            return jsonify(msg="❌ 'url' or 'current_url' is required to identify the camera"), 400
        normalized_url = camera_url.strip().upper()

        # Load the original camera doc
        camera_doc = db.cameras.find_one({"url": normalized_url})
        if not camera_doc:
            return jsonify(msg=f"❌ Camera with URL '{normalized_url}' not found"), 404

        allowed_keys = {"name", "username", "password", "new_url"}
        update_data = {}

        for key, value in data.items():
            if key not in allowed_keys:
                continue
            if not isinstance(value, str) or not value.strip():
                return jsonify(msg=f"❌ '{key}' must be a non-empty string"), 400
            if key == "new_url":
                new_url = value.strip().upper()
                # Check for conflict
                if db.cameras.find_one({"url": new_url}):
                    return jsonify(msg=f"❌ Camera with URL '{new_url}' already exists"), 409
                update_data["url"] = new_url
            elif key == "name":
                update_data["name"] = value.strip().upper()
            elif key == "username":
                update_data["username"] = value.strip()
            elif key == "password":
                update_data["password"] = bcrypt.hashpw(value.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        if not update_data:
            return jsonify(msg="❌ No valid fields provided to update"), 400

        db.cameras.update_one({"url": normalized_url}, {"$set": update_data})

        # Sync updated name/url in all stores
        if "url" in update_data or "name" in update_data:
            db.stores.update_many(
                {"cameras.url": normalized_url},
                {"$set": {
                    "cameras.$.url": update_data.get("url", normalized_url),
                    "cameras.$.name": update_data.get("name", camera_doc.get("name", ""))
                }}
            )

        updated_cam = db.cameras.find_one({"_id": camera_doc["_id"]})
        updated_cam["_id"] = str(updated_cam["_id"])
        return jsonify(msg="✅ Camera updated", camera=updated_cam)
    
        """
    Adds a store to a camera’s `stores` list if it doesn’t already exist.

    This endpoint checks:
    - If the camera with the provided URL exists
    - If the store exists in the stores collection
    - If the store is already in the camera’s stores list

    If all checks pass, it adds the store to the camera and adds the camera reference
    (`_id`, `url`, `name`) to the store’s `cameras` list. All comparisons are done using
    uppercase values for consistency. 

    ❌ It does not allow creating new stores or cameras here.
    
    Example `curl` request:
    ```bash
    curl -X POST https://116.203.203.86/cameras/add_store
    -H "Authorization: Bearer <JWT_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
        "url": "http://192.168.1.100:554",
        "store": "MAIN STORE"
    }'
    ```
    """

    @cameras_bp.route("/cameras/add_store", methods=["POST"])
    @jwt_required()
    def add_store_to_camera():
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify(msg="❌ Body cannot be empty"), 400

        cam_url = data.get("url", "").strip().upper()
        store_name = data.get("store", "").strip().upper()

        if not cam_url or not store_name:
            return jsonify(msg="❌ 'url' and 'store' are required"), 400

        cam = db.cameras.find_one({"url": cam_url})
        if not cam:
            return jsonify(msg=f"❌ Camera with URL '{cam_url}' not found"), 404

        if store_name in cam.get("stores", []):
            return jsonify(msg=f"ℹ️ Store '{store_name}' already in camera's list. No changes made."), 200

        store_doc = db.stores.find_one({"name": store_name})
        if not store_doc:
            return jsonify(msg=f"❌ Store '{store_name}' not found"), 404

        # Update camera
        db.cameras.update_one({"url": cam_url}, {"$addToSet": {"stores": store_name}})

        # Sync camera ref to store
        db.stores.update_one(
            {"name": store_name},
            {"$addToSet": {
                "cameras": {
                    "_id": cam["_id"],
                    "url": cam["url"],
                    "name": cam.get("name", "")
                }
            }}
        )

        return jsonify(msg=f"✅ Store '{store_name}' added to camera"), 200
    
        """
    Removes a store from a camera's stores list and syncs the store document to remove that camera.
    Input `url` and `store` are required and must be valid.
    - If the store is not in the camera's list, return a message.
    - If the store does not exist, return an error.
    - Syncs by removing the camera from the store's `cameras` array by `_id`.

    Example curl:
    curl -X POST https://116.203.203.86/cameras/remove_store
      -H "Authorization: Bearer <JWT_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{
        "url": "http://192.168.1.100:554",
        "store": "MAIN STORE"
    }'
    """
    @cameras_bp.route("/cameras/remove_store", methods=["POST"])
    @jwt_required()
    def remove_store_from_camera():
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify(msg="❌ Body cannot be empty"), 400

        url = data.get("url", "").strip().upper()
        store = data.get("store", "").strip().upper()

        if not url or not store:
            return jsonify(msg="❌ 'url' and 'store' are required"), 400

        cam = db.cameras.find_one({"url": url})
        if not cam:
            return jsonify(msg=f"❌ Camera with URL '{url}' not found"), 404

        if store not in cam.get("stores", []):
            return jsonify(msg=f"ℹ️ Store '{store}' not in camera stores list. Nothing to remove."), 200

        store_doc = db.stores.find_one({"name": store})
        if not store_doc:
            return jsonify(msg=f"❌ Store '{store}' not found"), 404

        db.cameras.update_one(
            {"_id": cam["_id"]},
            {"$pull": {"stores": store}}
        )

        db.stores.update_one(
            {"name": store},
            {"$pull": {"cameras": {"_id": cam["_id"]}}}
        )

        return jsonify(msg=f"✅ Store '{store}' removed from camera"), 200


    
    
    