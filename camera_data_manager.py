from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import List, Dict, Any, Iterable

import pytz
import os
from dotenv import load_dotenv
from pathlib import Path

from bson import ObjectId, errors as bson_errors
from pymongo.collection import Collection
from datetime import time, date
from logger import logger  # log to file and notify on error


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


# Read data retention limit from env
MAX_DATA_DAYS = int(os.getenv("MAX_DATA_DAYS", "1800"))

ISODate = str
HourEntry = Dict[str, Any]
DayBlock = Dict[ISODate, List[HourEntry]]


class CameraDataManager:
    def __init__(self, db):
        self.db = db
        self.col: Collection = db.camera_data
        self.tz = pytz.timezone("Europe/Zurich")

    def _normalise_ids(self, camera_id: str | Iterable[str]) -> List[str]:
        try:
            if isinstance(camera_id, (list, tuple, set)):
                return list({str(cid) for cid in camera_id})
            return [str(camera_id)]
        except Exception as e:
            logger.error(f"Failed to normalise camera_id(s): {e}")
            return []

    def _fetch_docs(self, cam_ids: List[str]) -> List[dict]:
        try:
            oid_list = [ObjectId(cid) for cid in cam_ids]
            return list(self.col.find({"camera_id": {"$in": oid_list}}))
        except bson_errors.InvalidId as e:
            logger.warning(f"Invalid camera ID(s): {e}")
        except Exception as e:
            logger.error(f"Error fetching documents: {e}")
        return []

    @staticmethod
    def _merge_regions(dest: Dict[str, Any], src: Dict[str, Any]) -> None:
        by_id = {r["id"]: r for r in dest["RegionList"]["Region"]}
        for r in src["RegionList"]["Region"]:
            rid = r["id"]
            if rid in by_id:
                tgt = by_id[rid]
                for key in ("enterCount", "exitCount", "passingCount"):
                    try:
                        tgt[key] = str(int(tgt[key]) + int(r[key]))
                    except Exception as e:
                        logger.warning(f"Region count merge failed: {e}")
            else:
                dest["RegionList"]["Region"].append(r.copy())

    @staticmethod
    def _merge_hour(dest: HourEntry, src: HourEntry) -> None:
        for key in ("enterCount", "exitCount", "peoplePassingCount", "duplicatePeopleCount"):
            try:
                dest[key] = str(int(dest[key]) + int(src[key]))
            except Exception as e:
                logger.warning(f"Hour count merge failed: {e}")
        CameraDataManager._merge_regions(dest, src)

    @classmethod
    def _aggregate_documents(cls, docs: List[dict]) -> Dict[ISODate, List[HourEntry]]:
        per_day: Dict[ISODate, Dict[str, HourEntry]] = defaultdict(dict)
        try:
            for d in docs:
                for block in d.get("data", []):
                    day_key, entries = next(iter(block.items()))
                    per_hour = per_day[day_key]
                    for entry in entries:
                        k = entry["timeSpan"]["startTime"]
                        if k in per_hour:
                            cls._merge_hour(per_hour[k], entry)
                        else:
                            per_hour[k] = entry.copy()
            return {
                day: sorted(list(hours.values()), key=lambda e: e["timeSpan"]["startTime"])
                for day, hours in per_day.items()
            }
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            return {}

    def create_data_doc(self, camera_id: str) -> ObjectId | None:
        try:
            doc = {"camera_id": ObjectId(camera_id), "data": []}
            return self.col.insert_one(doc).inserted_id
        except bson_errors.InvalidId as e:
            logger.warning(f"Invalid camera ID: {e}")
        except Exception as e:
            logger.error(f"Failed to create data doc: {e}")
        return None

    def upsert_data_by_date(self, camera_id: str, new_entry: DayBlock) -> None:
        try:
            cam_oid = ObjectId(camera_id)
            date_key = next(iter(new_entry))
            payload = new_entry[date_key]

            doc = self.col.find_one({"camera_id": cam_oid})
            if not doc:
                self.col.insert_one({"camera_id": cam_oid, "data": [{date_key: payload}]})
                return

            data_list = doc.get("data", [])
            for idx, blk in enumerate(data_list):
                if date_key in blk:
                    data_list[idx][date_key] = payload
                    break
            else:
                data_list.append({date_key: payload})

            today = dt.datetime.now(self.tz).date()
            cutoff = today - dt.timedelta(days=MAX_DATA_DAYS)
            data_list = [
                blk for blk in data_list
                if dt.datetime.strptime(next(iter(blk)), "%Y-%m-%d").date() >= cutoff
            ]

            self.col.update_one({"camera_id": cam_oid}, {"$set": {"data": data_list}})
        except bson_errors.InvalidId as e:
            logger.warning(f"Invalid camera ID during upsert: {e}")
        except Exception as e:
            logger.error(f"Upsert failed: {e}")

    def get_all_data(self, camera_id: str | Iterable[str]) -> Dict[ISODate, List[HourEntry]]:
        try:
            cam_ids = self._normalise_ids(camera_id)
            docs = self._fetch_docs(cam_ids)
            if not docs:
                return {}

            if len(docs) == 1:
                raw = docs[0].get("data", [])
                return {day: entries for block in raw for day, entries in block.items()}

            return self._aggregate_documents(docs)
        except Exception as e:
            logger.error(f"get_all_data failed: {e}")
            return {}

    def get_data_by_days(self, camera_id: str | Iterable[str], days_iso: List[ISODate]) -> Dict[ISODate, List[HourEntry]]:
        try:
            aggregate = self.get_all_data(camera_id)
            return {d: aggregate[d] for d in days_iso if d in aggregate}
        except Exception as e:
            logger.error(f"get_data_by_days failed: {e}")
            return {}

    def get_data_by_period(self, camera_id: str | Iterable[str], start_dt: date, end_dt: date) -> Dict[ISODate, List[HourEntry]]:
        try:
            result = {}
            for day, entries in self.get_all_data(camera_id).items():
                try:
                    day_obj = dt.datetime.strptime(day, "%Y-%m-%d").date()
                    if start_dt <= day_obj <= end_dt:
                        result[day] = entries
                except Exception as e:
                    logger.warning(f"Invalid day format in DB: {e}")
            return result
        except Exception as e:
            logger.error(f"get_data_by_period failed: {e}")
            return {}

    def get_data_by_time_range(self, camera_id: str | Iterable[str], date_iso: ISODate, start: time, end: time) -> Dict[ISODate, List[HourEntry]]:
        try:
            aggregated = self.get_all_data(camera_id).get(date_iso, [])
            filtered = []
            for e in aggregated:
                try:
                    t = dt.datetime.strptime(e["timeSpan"]["startTime"], "%Y-%m-%dT%H:%M:%S").time()
                    if start <= t <= end:
                        filtered.append(e)
                except Exception as e:
                    logger.warning(f"Bad time format in entry: {e}")
            return {date_iso: filtered}
        except Exception as e:
            logger.error(f"get_data_by_time_range failed: {e}")
            return {}

    def get_data_days_with_time_range(self, camera_id: str | Iterable[str], days_iso: List[ISODate], start: time, end: time) -> Dict[ISODate, List[HourEntry]]:
        try:
            output = {}
            aggregate = self.get_all_data(camera_id)
            for day in days_iso:
                if day not in aggregate:
                    continue
                output[day] = []
                for e in aggregate[day]:
                    try:
                        t = dt.datetime.strptime(e["timeSpan"]["startTime"], "%Y-%m-%dT%H:%M:%S").time()
                        if start <= t <= end:
                            output[day].append(e)
                    except Exception as e:
                        logger.warning(f"Time parse error in day {day}: {e}")
            return output
        except Exception as e:
            logger.error(f"get_data_days_with_time_range failed: {e}")
            return {}
