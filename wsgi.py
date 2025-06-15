# wsgi.py — WSGI entry point for Gunicorn production server
# Usage example: gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app

import os
from urllib.parse import quote_plus
from pymongo import MongoClient, errors
from dotenv import load_dotenv
from app import create_app

# Load .env file
load_dotenv()

# Get MongoDB credentials
user_raw = os.getenv("MONGO_INITDB_ROOT_USERNAME")
pwd_raw = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

if not user_raw or not pwd_raw:
    raise RuntimeError("Missing MongoDB credentials")

user = quote_plus(user_raw)
pwd = quote_plus(pwd_raw)

mongo_uri = f"mongodb://{user}:{pwd}@localhost:27020/?authSource=admin"

# Retry logic like in main.py (sync version)
def wait_for_mongo(uri, retries=5, delay=2):
    for _ in range(retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            return client
        except errors.ServerSelectionTimeoutError:
            import time
            time.sleep(delay)
    raise Exception("MongoDB not available")

client = wait_for_mongo(mongo_uri)
db = client["peoplecount"]

# Load secrets
env_docs = db.env.find({})
env_data = {doc["key"]: doc["value"] for doc in env_docs}

# Convert token expiry values to int
try:
    env_data["JWT_ACCESS_TOKEN_EXPIRES"] = int(env_data.get("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "60"))
except ValueError:
    env_data["JWT_ACCESS_TOKEN_EXPIRES"] = 60

try:
    env_data["JWT_REFRESH_TOKEN_EXPIRES"] = int(env_data.get("JWT_REFRESH_TOKEN_EXPIRES_SECONDS", "300"))
except ValueError:
    env_data["JWT_REFRESH_TOKEN_EXPIRES"] = 300

# Add DB reference
env_data["db"] = db

# Create Flask app
app = create_app(env_data)
