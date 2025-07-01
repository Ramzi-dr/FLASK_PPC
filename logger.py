import os
from datetime import datetime, timezone
import pytz
import asyncio
from pathlib import Path
import aiohttp

try:
    from notify import notify_HS
except ImportError:
    notify_HS = None  # Safe fallback if notify is missing

class DailyLogger:
    def __init__(self):
        self.timezone = pytz.timezone("Europe/Zurich")
        self.base_dir = Path(__file__).resolve().parent
        self.log_dir = self.base_dir / "log"
        self.startup_notified = False
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.log_dir = None

    def _now(self):
        try:
            return datetime.now(timezone.utc).astimezone(self.timezone)
        except Exception:
            return datetime.now().astimezone(self.timezone)

    def _get_log_file(self):
        self._ensure_log_dir()
        if not self.log_dir:
            return None
        now = self._now()
        filename = f"{now.strftime('%d.%m.%Y')}.log"
        return self.log_dir / filename

    def log(self, level, message):
        try:
            log_file = self._get_log_file()
            if not log_file:
                return
            now = self._now()
            entry = f"[{now.strftime('%H:%M:%S')}] [{level.upper()}] {message}\n"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
            self._enforce_log_limit()
        except Exception:
            pass

    def info(self, message):
        self.log("info", message)
    

    def warning(self, message):
        self.log("warning", message)
        self._notify_async(message)

    def error(self, message):
        self.log("error", message)
        self._notify_async(message)

    def critical(self, message):
        self.log("critical", message)
        self._notify_async(message)

    def _notify_async(self, message):
        if notify_HS is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(notify_HS(message, self))
        except RuntimeError:
            try:
                asyncio.run(notify_HS(message, self))
            except Exception:
                pass

    def _enforce_log_limit(self, limit=180):
        try:
            files = sorted(
                [f for f in self.log_dir.glob("*.log") if f.is_file()],
                key=lambda x: x.stat().st_mtime
            )
            while len(files) > limit:
                files.pop(0).unlink(missing_ok=True)
        except Exception:
            pass

    async def get_wan_ip(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.ipify.org?format=text", timeout=5) as resp:
                    return await resp.text()
        except Exception:
            return "unknown"

    async def notify_startup(self):
        if self.startup_notified or notify_HS is None:
            return
        try:
            now = self._now().strftime("%d.%m.%Y %H:%M:%S")
            ip = await self.get_wan_ip()
            msg = f"🚀 peoplecount backend started\n🕒 {now}\n🌐 IP: {ip}"
            await notify_HS(msg, self)
            self.startup_notified = True
        except Exception:
            pass

logger = DailyLogger()
