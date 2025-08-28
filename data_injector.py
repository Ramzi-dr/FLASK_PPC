import os
import json
import glob
import urllib.parse
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import pytz
import socket


def get_db():
    user = urllib.parse.quote_plus(os.getenv("MONGO_INITDB_ROOT_USERNAME"))
    pwd = urllib.parse.quote_plus(os.getenv("MONGO_INITDB_ROOT_PASSWORD"))
    db_name = os.getenv("MONGO_INITDB_DATABASE", "peoplecount")

    # Docker service host + port
    docker_host = os.getenv("MONGO_DOCKER_HOST", "peoplecount_flask-db")
    docker_port = int(os.getenv("MONGO_DOCKER_PORT", "27017"))

    # Fallback host + port (for host machine)
    fallback_host = os.getenv("MONGO_HOST", "127.0.0.1")
    fallback_port = int(os.getenv("MONGO_PORT", "27020"))

    # Try Docker hostname first
    try:
        socket.gethostbyname(docker_host)
        host, port = docker_host, docker_port
    except socket.gaierror:
        host, port = fallback_host, fallback_port

    uri = f"mongodb://{user}:{pwd}@{host}:{port}/{db_name}?authSource=admin"
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    print(f"✅ Connected to Mongo: {db_name} on {host}:{port}")
    return db


def extract_ip_from_filename(filename: str) -> str:
    decoded = urllib.parse.unquote(filename)
    parts = decoded.split("/")
    for part in parts:
        if part.count(".") == 3:
            return part
    return None


def extract_ip_from_url(url: str) -> str:
    decoded = urllib.parse.unquote(url)
    parts = decoded.split("/")
    for part in parts:
        if part.count(".") == 3:
            return part
    return None


def inject_all_files():
    print("🏁 Starting JSON data bulk injector")
    db = get_db()
    tz = pytz.timezone("Europe/Zurich")

    # Build ip -> camera mapping
    camera_map = {}
    for cam in db.cameras.find():
        ip = extract_ip_from_url(cam.get("url", ""))
        if ip:
            camera_map[ip] = cam

    for file in glob.glob("cam_data/*.json"):
        ip = extract_ip_from_filename(file)
        if not ip:
            print(f"⚠️ Skipping {file}, no IP found")
            continue
        if ip not in camera_map:
            print(f"⚠️ No camera found for {ip}")
            continue

        try:
            with open(file, "r") as f:
                payload = json.load(f)

            cam = camera_map[ip]
            cam_oid = ObjectId(cam["_id"])

            # --- CLEAN: remove stray top-level date fields ---
            bad_fields = {k: "" for k in payload if isinstance(k, str) and k.count("-") == 2}
            if bad_fields:
                db.camera_data.update_one({"camera_id": cam_oid}, {"$unset": bad_fields})
                print(f"🧹 Cleaned stray fields for {cam['name']}")

            # --- Append only (skip if already exists) ---
            for date_key, entries in payload.items():
                if not isinstance(entries, list):
                    continue

                doc = db.camera_data.find_one({"camera_id": cam_oid})
                if not doc:
                    db.camera_data.insert_one({"camera_id": cam_oid, "data": [{date_key: entries}]})
                    print(f"➕ Created new doc for {cam['name']} {date_key} ({len(entries)} entries)")
                    continue

                data_list = doc.get("data", [])
                exists = any(date_key in blk for blk in data_list)
                if exists:
                    print(f"⏩ Skipped {date_key} for {cam['name']} (already exists)")
                    continue

                data_list.append({date_key: entries})

                # retention ~5 years
                today = datetime.now(tz).date()
                cutoff = today.replace(year=today.year - 5)
                data_list = [
                    blk for blk in data_list
                    if datetime.strptime(next(iter(blk)), "%Y-%m-%d").date() >= cutoff
                ]

                db.camera_data.update_one({"camera_id": cam_oid}, {"$set": {"data": data_list}})
                print(f"➕ Added {date_key} for {cam['name']} ({len(entries)} entries)")

        except Exception as e:
            print(f"❌ Failed for {file}: {e}")


if __name__ == "__main__":
    inject_all_files()
