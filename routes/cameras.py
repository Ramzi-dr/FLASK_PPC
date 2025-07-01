""" cameras.py """

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import re
from logger import logger
from camera_data_manager import CameraDataManager

cameras_bp = Blueprint("cameras", __name__)
url_regex = re.compile(
    r"^(https?|wss?):\/\/([A-Z0-9\-\.]+|\[[A-F0-9:]+\])(?::(\d+))?(\/[^\s]*)?$",
    re.IGNORECASE,
)


def init_camera_routes(db):

    # ---------- GET ----------
    @cameras_bp.route("/cameras", methods=["GET"])
    @jwt_required()
    def get_all_cameras():
        try:
            cameras = db.cameras.find(
                {},
                {
                    "_id": 1,
                    "url": 1,
                    "username": 1,
                    "name": 1,
                    "stores": 1,
                    "data_id": 1,
                },
            )
            result = []
            for cam in cameras:
                cam["_id"] = str(cam["_id"])
                cam["data_id"] = (
                    str(cam.get("data_id", "")) if cam.get("data_id") else ""
                )
                result.append(cam)
            logger.info("✅ Cameras fetched")
            return jsonify(result)
        except Exception as e:
            logger.critical(f"GET /cameras failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    # ---------- POST ----------

    @cameras_bp.route("/cameras", methods=["POST"])
    @jwt_required()
    def create_camera():
        try:
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
                return jsonify(msg="❌ Invalid URL format"), 400

            normalized_url = url.upper()
            normalized_store = store_name.upper() if store_name else None
            normalized_name = name.upper() if name else ""

            if db.cameras.find_one({"url": normalized_url}):
                return (
                    jsonify(msg=f"❌ Camera with URL '{normalized_url}' already exists"),
                    409,
                )

            stores_list = []
            if normalized_store:
                store_doc = db.stores.find_one({"name": normalized_store})
                if not store_doc:
                    return jsonify(msg=f"❌ Store '{normalized_store}' not found"), 404
                stores_list.append(normalized_store)

            cam_doc = {
                "url": normalized_url,
                "username": username,
                "password": password,  # store plain text
                "stores": stores_list,
                "name": normalized_name,
            }
            cam_id = db.cameras.insert_one(cam_doc).inserted_id

            data_id = CameraDataManager(db).create_data_doc(cam_id)
            db.cameras.update_one({"_id": cam_id}, {"$set": {"data_id": data_id}})

            if normalized_store:
                db.stores.update_one(
                    {"name": normalized_store},
                    {
                        "$addToSet": {
                            "cameras": {
                                "name": normalized_name,
                                "_id": cam_id,
                                "url": normalized_url,
                            }
                        }
                    },
                )

            updated = db.cameras.find_one({"_id": cam_id}, {"password": 0})
            updated["_id"] = str(updated["_id"])
            updated["data_id"] = str(updated.get("data_id", ""))

            logger.info(f"✅ Camera created: {normalized_url}")
            return jsonify(msg="✅ Camera created", camera=updated), 201
        except Exception as e:
            logger.critical(f"POST /cameras failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    @cameras_bp.route("/cameras", methods=["PUT"])
    @jwt_required()
    def update_camera():
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify(msg="❌ Body cannot be empty"), 400
            if "stores" in data:
                return (
                    jsonify(
                        msg="❌ Camera stores list must be edited via /cameras/add_store or remove_store"
                    ),
                    400,
                )

            cam_url = data.get("current_url") or data.get("url")
            if not cam_url:
                return jsonify(msg="❌ 'url' or 'current_url' is required"), 400
            normalized_url = cam_url.strip().upper()
            camera_doc = db.cameras.find_one({"url": normalized_url})
            if not camera_doc:
                return jsonify(msg=f"❌ Camera '{normalized_url}' not found"), 404

            allowed = {"name", "username", "password", "new_url"}
            update = {}
            for k, v in data.items():
                if k not in allowed or not isinstance(v, str) or not v.strip():
                    continue
                if k == "new_url":
                    new_url = v.strip().upper()
                    if db.cameras.find_one({"url": new_url}):
                        return (
                            jsonify(msg=f"❌ Camera with URL '{new_url}' already exists"),
                            409,
                        )
                    update["url"] = new_url
                elif k == "name":
                    update["name"] = v.strip().upper()
                elif k == "username":
                    update["username"] = v.strip()
                elif k == "password":
                    update["password"] = v.strip()  # store plain text

            if not update:
                return jsonify(msg="❌ No valid fields to update"), 400

            db.cameras.update_one({"url": normalized_url}, {"$set": update})

            if "url" in update or "name" in update:
                db.stores.update_many(
                    {"cameras.url": normalized_url},
                    {
                        "$set": {
                            "cameras.$.url": update.get("url", normalized_url),
                            "cameras.$.name": update.get(
                                "name", camera_doc.get("name", "")
                            ),
                        }
                    },
                )

            updated_cam = db.cameras.find_one({"_id": camera_doc["_id"]}, {"password": 0})
            updated_cam["_id"] = str(updated_cam["_id"])
            updated_cam["data_id"] = (
                str(updated_cam.get("data_id", "")) if updated_cam.get("data_id") else ""
            )

            logger.info(f"✅ Camera updated: {normalized_url}")
            return jsonify(msg="✅ Camera updated", camera=updated_cam)
        except Exception as e:
            logger.critical(f"PUT /cameras failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500

    # ---------- DELETE ----------


    @cameras_bp.route("/cameras", methods=["DELETE"])
    @jwt_required()
    def delete_camera():
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify(msg="❌ Body cannot be empty"), 400

            url = data.get("url", "").strip().upper()
            name = data.get("name", "").strip().upper()

            if not url and not name:
                return jsonify(msg="❌ 'url' or 'name' is required"), 400

            cam_doc = None
            if url:
                cam_doc = db.cameras.find_one({"url": url})
                if not cam_doc:
                    return jsonify(msg=f"❌ No camera found with URL '{url}'"), 404
            elif name:
                matches = list(db.cameras.find({"name": name}))
                if len(matches) == 0:
                    return jsonify(msg=f"❌ No camera found with name '{name}'"), 404
                if len(matches) > 1:
                    return (
                        jsonify(
                            msg="❌ This name is assigned to more than one camera. Use 'url' instead."
                        ),
                        400,
                    )
                cam_doc = matches[0]

            cam_id = cam_doc["_id"]
            cam_url = cam_doc["url"]

            # 🧹 Remove from all store camera lists
            db.stores.update_many(
                {"cameras.url": cam_url},
                {"$pull": {"cameras": {"url": cam_url}}},
            )

            # 🧹 Remove from camera_data collection
            db.camera_data.delete_many({"camera_id": cam_id})

            # 🗑️ Remove camera itself
            db.cameras.delete_one({"_id": cam_id})

            logger.info(f"✅ Deleted camera '{cam_url}' and its camera_data entry.")
            return jsonify(msg=f"✅ Camera '{cam_url}' deleted successfully"), 200

        except Exception as e:
            logger.critical(f"DELETE /cameras failed: {e}")
            return jsonify(msg="❌ Internal server error"), 500
