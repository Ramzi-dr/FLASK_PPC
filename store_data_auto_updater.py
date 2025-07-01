# store_data_auto_updater.py

import asyncio
import time
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from camera_data_manager import CameraDataManager
from data_updater import DataUpdater
from logger import logger
from urllib.parse import quote_plus
from typing import Any, Dict
import pytz
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

load_dotenv()
logger.info("✅ Environment variables loaded for store_data_auto_updater")

MONGO_USER = os.getenv("MONGO_INITDB_ROOT_USERNAME")
MONGO_PASS = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
MONGO_HOST = os.getenv("MONGO_DOCKER_HOST", "peoplecount_flask-db")
MONGO_PORT = os.getenv("MONGO_DOCKER_PORT", "27027")
MONGO_DB = os.getenv("MONGO_INITDB_DATABASE", "peoplecount")

# Build Mongo URI
try:
    user = quote_plus(MONGO_USER)
    pwd = quote_plus(MONGO_PASS)
    uri = f"mongodb://{user}:{pwd}@{MONGO_HOST}:{MONGO_PORT}/"
except Exception as e:
    logger.critical(f"❌ Failed to build Mongo URI: {e}")
    raise


def is_store_open(store: Dict[str, Any]) -> bool:
    try:
        zurich_now = datetime.now(pytz.timezone("Europe/Zurich")).time()
        open_str = store.get("open_time")
        close_str = store.get("close_time")

        if not open_str or not close_str:
            return True  # open 24/7

        open_time = datetime.strptime(open_str, "%H:%M").time()
        close_time = datetime.strptime(close_str, "%H:%M").time()

        if open_time <= close_time:
            return open_time <= zurich_now <= close_time
        else:
            return zurich_now >= open_time or zurich_now <= close_time

    except Exception as e:
        logger.error(f"⚠️ Error checking store hours: {repr(e)}")
        return True


async def update_open_stores_cameras():
    logger.info("🔄 Updating cameras from currently open stores")

    try:
        client = MongoClient(uri)
        db = client[MONGO_DB]
        manager = CameraDataManager(db)
        stores = list(db.stores.find({}))

        tasks = []
        sem = asyncio.Semaphore(4)  # Limit to 4 concurrent updates

        for store in stores:
            if not is_store_open(store):
                logger.info(f"🕒 Store '{store.get('name', '?')}' is closed, skipping")
                continue

            cams = store.get("cameras", [])
            if not cams:
                logger.info(f"⚠️ Store '{store.get('name', '?')}' has no cameras")
                continue

            for cam in cams:
                cam_id = cam.get("_id")
                cam_url = cam.get("url")
                if not cam_id or not cam_url:
                    logger.warning(f"⚠️ Skipping camera with missing _id or url: {cam}")
                    continue

                camera = db.cameras.find_one({"_id": ObjectId(cam_id)})
                if not camera:
                    logger.warning(f"⚠️ Camera not found in DB: {cam_id}")
                    continue

                updater = DataUpdater(
                    cam_url, camera.get("username", ""), camera.get("password", "")
                )

                async def fetch_and_store(up=updater, cid=str(cam_id), curl=cam_url):
                    try:
                        data_dict = up.get_today_data()
                    except Exception as e:
                        logger.error(f"❌ Fetch failed for {curl}: {repr(e)}")
                        return

                    if not isinstance(data_dict, dict):
                        logger.error(f"❌ Invalid fetch result from {curl}")
                        return

                    for date_str, data in data_dict.items():
                        if isinstance(data, list):
                            try:
                                manager.upsert_data_by_date(cid, {date_str: data})
                                logger.info(f"✅ {curl} updated with {len(data)} entries")
                            except Exception as e:
                                logger.error(f"❌ DB write failed for {curl}: {repr(e)}")
                        else:
                            logger.error(f"❌ Bad format from {curl}: {repr(data)}")

                async def limited(task):
                    async with sem:
                        await task

                tasks.append(limited(fetch_and_store()))

        await asyncio.gather(*tasks)
        logger.info("✅ Finished updating all open store cameras")

    except Exception as e:
        logger.critical(f"❌ Unexpected error in update: {repr(e)}")
