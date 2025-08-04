import os
import aiohttp
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

AUTH_USER = os.getenv("AUTH_USER")
AUTH_PASS = os.getenv("AUTH_PASS")
RECEIVER_EMAIL = os.getenv("NOTIFICATION_RECEIVER_EMAIL")
TITLE = os.getenv("NOTIFICATION_TITLE")
NOTIFY_LOGIN_URL = os.getenv("NOTIFY_LOGIN_URL", "http://hs_notifier:3000/login")
NOTIFY_URL = os.getenv("NOTIFY_ENDPOINT_URL", "http://hs_notifier:3000/notifier")

MAX_RETRIES = 10
RETRY_BASE_DELAY = 2  # seconds

# Flag to track if notify_HS was called for the first time
_first_time_called = True

async def notify_HS(message, logger=None, email=None):
    """
    Sends a notification via external service using Microsoft email account.
    Includes robust retry logic for connection errors.
    Waits 2 seconds only on the first call.
    Never raises unhandled errors if hs_notifier is unavailable.

    Args:
        message (str): The message body (HTML allowed).
        logger (optional): Logger instance.
        email (str, optional): Email to override default receiver.
    """
    global _first_time_called
    if _first_time_called:
        await asyncio.sleep(2)
        _first_time_called = False

    receiver = (email if email else RECEIVER_EMAIL or "").strip().lower()



    for attempt in range(1, MAX_RETRIES + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                login_payload = {"username": AUTH_USER, "password": AUTH_PASS}
                try:
                    async with session.post(
                        NOTIFY_LOGIN_URL, json=login_payload, ssl=False
                    ) as resp:
                        if resp.status != 200:
                            raise Exception(f"Login failed HTTP {resp.status}")
                        data = await resp.json()
                        token = data.get("token")
                        if not token:
                            raise Exception("Login succeeded but token missing")
                        if logger:
                            logger.info("✅ Login OK, token received")
                except Exception as e:
                    await asyncio.sleep(2)
                    raise Exception(f"Login request failed: {e}")

                headers = {"Authorization": f"Bearer {token}"}
                payload = {
                    "receiver": receiver,
                    "title": TITLE,
                    "message": message,
                }
                try:
                    async with session.post(
                        NOTIFY_URL, json=payload, headers=headers, ssl=False
                    ) as resp:
                        res_data = await resp.json()
                        if resp.status != 200:
                            raise Exception(
                                f"Notify failed: {resp.status} → {res_data}"
                            )
                        if logger:
                            logger.info(f"✅ Notification sent: {res_data}")
                    return  # success
                except Exception as e:
                    raise Exception(f"Notify request failed: {e}")

        except Exception as e:
            if logger:
                logger.error(f"❌ Attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BASE_DELAY * attempt)
            else:
                if logger:
                    logger.warning("⚠️ hs_notifier unavailable, giving up after retries")
                return  # fail silently after retries
