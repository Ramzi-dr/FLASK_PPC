"""
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
import asyncio
import os
from pymongo import MongoClient, errors
from dotenv import load_dotenv
from app import create_app
from urllib.parse import quote_plus
from logger import logger
from store_data_auto_updater import update_open_stores_cameras
from pathlib import Path
from notify import notify_HS
import aiohttp

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


async def get_wan_ip():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.ipify.org?format=text", timeout=5) as resp:
                return await resp.text()
    except:
        return "unknown"


async def wait_for_mongo(uri, retries=5, delay=2):
    for i in range(retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            logger.info("✅ MongoDB connection successful.")
            return client
        except errors.ServerSelectionTimeoutError as e:
            logger.warning(f"🕒 MongoDB not ready (attempt {i+1}/{retries}): {e}")
            await asyncio.sleep(delay)

    logger.critical("❌ MongoDB not reachable after multiple attempts.")
    raise Exception("MongoDB not available")


async def periodic_store_update():
    await asyncio.sleep(300)  # initial delay after manual update
    while True:
        try:
            await update_open_stores_cameras()
        except Exception as e:
            logger.error(f"❌ Background store update failed: {repr(e)}")
        await asyncio.sleep(300)


async def run_flask(app):
    try:
        await asyncio.to_thread(app.run, host="0.0.0.0", port=5000)
    except Exception as e:
        logger.critical(f"❌ Flask server crashed: {repr(e)}")
        try:
            wan_ip = await get_wan_ip()
            await notify_HS(f"❌ Flask crashed: {repr(e)}\n🌐 WAN IP: {wan_ip}", logger)
        except Exception as notify_err:
            logger.error(f"❌ Failed to notify: {notify_err}")


async def start():
    try:
        user = quote_plus(os.getenv("MONGO_INITDB_ROOT_USERNAME", ""))
        pwd = quote_plus(os.getenv("MONGO_INITDB_ROOT_PASSWORD", ""))
        MONGO_URL =os.getenc("MONGO_DOCKER_HOST", "peoplecount-db")
        MONGO_PORT = os.getenv("MONGO_DOCKER_PORT", "27017")

        mongo_uri = f"mongodb://{user}:{pwd}@{MONGO_URL}:{MONGO_PORT}/?authSource=admin"

        client = await wait_for_mongo(mongo_uri)
        db = client["peoplecount"]
        logger.info("✅ Connected to MongoDB and selected database.")

        env_data = {doc["key"]: doc["value"] for doc in db.env.find({})}
        env_data["db"] = db

        try:
            env_data["JWT_ACCESS_TOKEN_EXPIRES"] = int(
                env_data.get("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "60")
            )
        except ValueError:
            env_data["JWT_ACCESS_TOKEN_EXPIRES"] = 60
            logger.warning("⚠️ Invalid JWT_ACCESS_TOKEN_EXPIRES_SECONDS, using 60.")

        try:
            env_data["JWT_REFRESH_TOKEN_EXPIRES"] = int(
                env_data.get("JWT_REFRESH_TOKEN_EXPIRES_SECONDS", "300")
            )
        except ValueError:
            env_data["JWT_REFRESH_TOKEN_EXPIRES"] = 300
            logger.warning("⚠️ Invalid JWT_REFRESH_TOKEN_EXPIRES_SECONDS, using 300.")

        app = create_app(env_data)
        logger.info("🚀 Flask app created")

        await update_open_stores_cameras()

        wan_ip = await get_wan_ip()
        await notify_HS(f"🚀 peoplecount backend started\n🌐 WAN IP: {wan_ip}", logger)

        await asyncio.gather(
            run_flask(app),
            periodic_store_update(),
        )

    except Exception as e:
        logger.critical(f"❌ App startup failed: {repr(e)}")
        try:
            wan_ip = await get_wan_ip()
            await notify_HS(f"❌ App startup failed: {repr(e)}\n🌐 WAN IP: {wan_ip}", logger)
        except Exception as notify_err:
            logger.error(f"❌ Failed to notify: {notify_err}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        logger.warning("🛑 Server shutdown requested.")
        try:
            wan_ip = asyncio.run(get_wan_ip())
            msg = f"🛑 Server shutdown requested.\n🌐 WAN IP: {wan_ip}"
            asyncio.run(notify_HS(msg, logger))
        except Exception as e:
            logger.error(f"❌ Failed to send shutdown email: {e}")
    except Exception as e:
        logger.critical(f"❌ App crashed: {repr(e)}")
        try:
            wan_ip = asyncio.run(get_wan_ip())
            msg = f"❌ App crashed: {repr(e)}\n🌐 WAN IP: {wan_ip}"
            asyncio.run(notify_HS(msg, logger))
        except Exception as e:
            logger.error(f"❌ Failed to send crash email: {e}")
