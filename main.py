""" """
main.py — Async entry point for the Flask application

This file initializes your Flask app securely and reliably by:
- Loading MongoDB credentials from a `.env` file
- Waiting for MongoDB to become ready before proceeding
- Loading secrets from the `env` collection in MongoDB
- Injecting those secrets into the Flask app
- Launching the Flask app

✅ This keeps Flask clean and separates logic from setup

REQUIREMENTS (install with pip):
    pip install pymongo python-dotenv

OTHER CONFIG NEEDED:
    - `.env` file must contain:
        MONGO_INITDB_ROOT_USERNAME=...
        MONGO_INITDB_ROOT_PASSWORD=...
    - MongoDB must have a database called `peoplecount` and a collection `env`
        with documents like: { "key": "FLASK_USER", "value": "AdminHS" }, etc.
"""

# Async support for retry logic
import asyncio

# Access to environment variables like DB user/pass
import os

# MongoDB client + connection error types
from pymongo import MongoClient, errors

# Load .env file automatically
from dotenv import load_dotenv

# Import the app factory function from app.py
from app import create_app

# For safe encoding of special characters in MongoDB password
from urllib.parse import quote_plus

# Load environment variables from `.env` into memory
load_dotenv()


async def wait_for_mongo(uri, retries=5, delay=2):
    """
    Try to connect to MongoDB with retries.

    If the DB is not yet ready (e.g. in Docker), it will retry every `delay` seconds
    up to `retries` times.
    """
    for _ in range(retries):
        try:
            # Create a test client with a short timeout
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)

            # Try to ping the server
            client.admin.command("ping")
            return client

        except errors.ServerSelectionTimeoutError:
            # Wait before trying again
            await asyncio.sleep(delay)

    # After all retries fail, raise a fatal error
    raise Exception("MongoDB not available")


async def start():
    """
    Main startup routine:
    - Builds MongoDB URI from .env
    - Waits for DB to be available
    - Loads app secrets from DB
    - Starts the Flask server
    """
    # Read DB username/password from .env file
    user = quote_plus(os.getenv("MONGO_INITDB_ROOT_USERNAME"))
    pwd = quote_plus(os.getenv("MONGO_INITDB_ROOT_PASSWORD"))

    # MongoDB URI
    # If Flask runs in Docker, use container name (uncomment the line below)
    # mongo_uri = f"mongodb://{user}:{pwd}@peoplecount-db:27017/?authSource=admin"

    # If Flask runs locally, connect to mapped port
    mongo_uri = f"mongodb://{user}:{pwd}@localhost:27020/?authSource=admin"

    # Wait for DB to be ready
    client = await wait_for_mongo(mongo_uri)
    # Connect to specific DB
    db = client["peoplecount"]

    # Load all secrets as key-value pairs into a Python dict
    env_data = {doc["key"]: doc["value"] for doc in db.env.find({})}

    # Inject DB itself for use in routes (e.g. /stores)
    env_data["db"] = db

    # Create Flask app with those secrets
    app = create_app(env_data)

    # Start the web server
    app.run(host="localhost", port=5000)


# Only run if script is executed directly (not imported)
if __name__ == "__main__":
    asyncio.run(start())
 """