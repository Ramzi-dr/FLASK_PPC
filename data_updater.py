import os
import time
import requests
import xmltodict
from datetime import datetime
from pymongo import MongoClient
from camera_data_manager import CameraDataManager
from logger import logger
from urllib.parse import quote_plus
from requests.auth import HTTPDigestAuth
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# MongoDB setup
MONGO_USER = os.getenv("MONGO_INITDB_ROOT_USERNAME")
MONGO_PASS = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
MONGO_PORT = os.getenv("MONGO_DOCKER_PORT", "27017")
MONGO_URL = os.getenv("MONGO_DOCKER_HOST", "peoplecount-db")
MONGO_DB = os.getenv("MONGO_INITDB_DATABASE", "peoplecount")

# Build Mongo URI
try:
    user = quote_plus(MONGO_USER)
    pwd = quote_plus(MONGO_PASS)
    uri = f"mongodb://{user}:{pwd}@{MONGO_URL}:{MONGO_PORT}/"
except Exception as e:
    logger.critical(f"❌ Could not build Mongo URI: {e}")
    exit(1)


class DataUpdater:
    def __init__(self, url, username, password):
        self.url = url
        self.auth = (username, password)
        self.today = datetime.now().strftime("%Y-%m-%d")

    def _build_xml_payload(self):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<CountingStatisticsDescription>
  <statisticType>all</statisticType>
  <reportType>daily</reportType>
  <timeSpanList><timeSpan>
    <startTime>{self.today}T00:00:00</startTime>
    <endTime>{self.today}T23:59:59</endTime>
  </timeSpan>
  </timeSpanList>
  <regionID>1,2,3,4,5</regionID>
</CountingStatisticsDescription>"""

    def fetch(self, attempt=1):
        try:
            res = requests.post(
                self.url,
                data=self._build_xml_payload(),
                headers={"Content-Type": "application/xml"},
                auth=HTTPDigestAuth(*self.auth),
                timeout=10,
            )
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if res.status_code == 401 and attempt < 3:
                logger.warning(f"[Attempt {attempt}] 401 Unauthorized for {self.url}")
                time.sleep(2)
                return self.fetch(attempt + 1)
            logger.warning(f"❌ HTTP error for {self.url}: {e}")
            return []
        except requests.exceptions.RequestException as e:
            if attempt < 3:
                logger.warning(f"🔁 Retry {attempt}/3 for {self.url} due to: {e}")
                time.sleep(2)
                return self.fetch(attempt + 1)
            logger.warning(f"❌ Request failed for {self.url}: {e}")
            return []

        if not res.text.strip():
            logger.warning(f"⚠️ Empty XML response from {self.url}")
            return []

        try:
            data = xmltodict.parse(res.text)
        except Exception as e:
            logger.warning(f"⚠️ XML parse error from {self.url}: {e}")
            logger.debug(f"Raw response: {res.text!r}")
            return []

        result = data.get("CountingStatisticsResult", {})
        if (
            result.get("responseStatus") == "true"
            and result.get("responseStatusStrg") == "OK"
        ):
            matches = result.get("matchList", {}).get("matchElement", [])
            return matches if isinstance(matches, list) else [matches]

        logger.warning(f"⚠️ Unexpected response from {self.url}: {result}")
        return []

    def get_today_data(self):
        data = self.fetch()
        return {self.today: data}


def update_all_cameras():
    logger.info("🏁 Starting data update script")
    try:
        logger.info("🚀 Connecting to MongoDB")
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB]
        manager = CameraDataManager(db)

        cameras = db.cameras.find({}, {"_id": 1, "url": 1, "username": 1, "password": 1})
        if cameras is None:
            logger.critical("❌ cameras.find() returned None")
            return

        found = False
        for cam in cameras:
            found = True
            try:
                cam_id = str(cam["_id"])
            except Exception as e:
                logger.warning(f"⚠️ Skipping invalid camera ID: {e}")
                continue

            cam_url = cam.get("url", "unknown")
            logger.info(f"📸 Processing camera: {cam_url}")

            try:
                updater = DataUpdater(cam_url, cam["username"], cam["password"])
                data_dict = updater.get_today_data()

                for date_str, data in data_dict.items():
                    if not isinstance(data, list):
                        logger.warning(f"⚠️ Invalid data format for {cam_url} on {date_str}")
                        continue

                    if data:
                        logger.info(f"👉 Sample data: {data[0]}")
                    else:
                        logger.warning(f"⚠️ Empty data list for {cam_url} on {date_str}")

                    try:
                        manager.upsert_data_by_date(cam_id, {date_str: data})
                        logger.info(f"📊 Inserted {len(data)} records for {cam_url} on {date_str}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to insert data for {cam_url} on {date_str}: {e}")

                logger.info(f"✅ Camera updated: {cam_url}")

            except Exception as e:
                logger.warning(f"⚠️ Failed to update camera {cam_url}: {repr(e)}")

        if not found:
            logger.warning("⚠️ No cameras found in database")

    except Exception as e:
        logger.critical(f"❌ Could not connect or run update_all_cameras: {repr(e)}")



