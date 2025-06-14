# wsgi.py — WSGI entry point for Gunicorn production server

from dotenv import load_dotenv
import os
from urllib.parse import quote_plus
from app import create_app

# Load environment variables from .env file
load_dotenv()

user_raw = os.getenv("MONGO_INITDB_ROOT_USERNAME")
pwd_raw = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

if user_raw is None or pwd_raw is None:
    raise RuntimeError("Missing MongoDB credentials in environment variables")

user = quote_plus(user_raw)
pwd = quote_plus(pwd_raw)

# Build MongoDB URI
mongo_uri = f"mongodb://{user}:{pwd}@localhost:27020/?authSource=admin"

# Import pymongo here to avoid import errors before loading env
from pymongo import MongoClient

client = MongoClient(mongo_uri)
db = client["peoplecount"]

# Load secrets from env collection as a dict
env_docs = db.env.find({})
env_data = {doc["key"]: doc["value"] for doc in env_docs}

# Inject DB object
env_data["db"] = db

# Create Flask app with loaded environment
app = create_app(env_data)
