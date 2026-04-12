import os
import time
import re
import logging
import requests
from requests.exceptions import ReadTimeout, ConnectionError, RequestException
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY") or os.getenv("API_KEY")

TELEGRAM_CONNECT_TIMEOUT = int(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "10"))
TELEGRAM_READ_TIMEOUT = int(os.getenv("TELEGRAM_READ_TIMEOUT", "60"))
TELEGRAM_LONG_POLL_TIMEOUT = int(os.getenv("TELEGRAM_LONG_POLL_TIMEOUT", "30"))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "20"))

if not BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("telegram-bot")

session = requests.Session()


def tg(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    response = session.post(
        url,
        json=payload,
        timeout=(TELEGRAM_CONNECT_TIMEOUT, TELEGRAM_READ_TIMEOUT),
    )
    response.raise_for_status()
    return response.json()


def api(method, path, json_body=None):
    url = API_BASE_URL.rstrip("/") + path
    headers = {}
    if INTERNAL_API_KEY:
        headers["X-API-KEY"] = INTERNAL_API_KEY
    response = session.request(
        method,
        url,
        json=json_body,
        headers=headers,
        timeout=API_TIMEOUT,
    )
    return response


def safe_send(chat_id, text):
    try:
        tg("sendMessage", {"chat_id": chat_id, "text": text})
    except RequestException as exc:
        logger.exception("Failed to send Telegram message to chat_id=%s: %s", chat_id, exc)


def parse_kv(text):
    data = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        data[k.strip().lower()] = v.strip()
    return data


def handle_start(chat_id, username, text):
    m = re.match(r"^/start\s+(\d+)$", text.strip())
    if not m:
        safe_send(
            chat_id,
            "Hi! To link you to a patient record, send: /start <patient_id>\nExample: /start 3",
        )
        return

    patient_id = int(m.group(1))
    try:
        resp = api(
            "POST",
            f"/patients/{patient_id}/link-telegram",
            {
                "telegram_chat_id": str(chat_id),
                "telegram_username": username,
            },
        )
    except RequestException as exc:
        logger.exception("API error while linking patient_id=%s: %s", patient_id, exc)
        safe_send(chat_id, "Linking failed because the clinic server could not be reached. Please try again shortly.")
        return

    if resp.status_code == 200:
        safe_send(chat_id, f"Linked to patient_id={patient_id}. You can now submit responses.")
    else:
        safe_send(chat_id, f"Linking failed: {resp.status_code} {resp.text}")


def handle_response(chat_id, text):
    try:
        lookup = api("GET", f"/patients/by-telegram/{chat_id}")
    except RequestException as exc:
        logger.exception("API lookup failed for chat_id=%s: %s", chat_id, exc)
        safe_send(chat_id, "The clinic server is temporarily unavailable. Please try again later.")
        return

    if lookup.status_code != 200:
        safe_send(chat_id, "You're not linked yet. Send: /start <patient_id>")
        return

    patient = lookup.json()
    patient_id = patient["patient_id"]

    kv = parse_kv(text)
    required = ["adherence", "difficulty_level", "pain_level", "progress_perception"]
    if not all(k in kv and kv[k] for k in required):
        safe_send(
            chat_id,
            "Invalid format. Reply like:\nadherence: 4\ndifficulty_level: 2\npain_level: 1\nprogress_perception: Better\nnon_compliance: (optional)\nissues: (optional)\nnotes: (optional)",
        )
        return

    try:
        payload = {
            "patient_id": patient_id,
            "adherence": int(kv["adherence"]),
            "difficulty_level": int(kv["difficulty_level"]),
            "pain_level": int(kv["pain_level"]),
            "progress_perception": kv["progress_perception"],
            "non_compliance": kv.get("non_compliance") or None,
            "issues": kv.get("issues") or None,
            "notes": kv.get("notes") or None,
        }
    except ValueError:
        safe_send(chat_id, "adherence, difficulty_level, and pain_level must be numbers.")
        return

    try:
        resp = api("POST", "/responses", payload)
    except RequestException as exc:
        logger.exception("API save failed for patient_id=%s: %s", patient_id, exc)
        safe_send(chat_id, "Failed to save because the clinic server could not be reached. Please try again shortly.")
        return

    if resp.status_code == 201:
        safe_send(chat_id, "Saved — thank you!")
    else:
        safe_send(chat_id, f"Failed to save: {resp.status_code} {resp.text}")


def poll_loop():
    offset = None
    backoff_seconds = 3

    while True:
        payload = {"timeout": TELEGRAM_LONG_POLL_TIMEOUT}
        if offset is not None:
            payload["offset"] = offset

        try:
            updates = tg("getUpdates", payload)
            backoff_seconds = 3
        except (ReadTimeout, ConnectionError) as exc:
            logger.warning("Telegram polling timeout/network error: %s", exc)
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)
            continue
        except RequestException as exc:
            logger.exception("Telegram polling request failed: %s", exc)
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)
            continue

        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message")
            if not msg:
                continue

            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            username = chat.get("username")
            text = msg.get("text", "")
            if not chat_id or not text:
                continue

            logger.info("Received message from chat_id=%s text=%r", chat_id, text)

            if text.strip().startswith("/start"):
                handle_start(chat_id, username, text)
            else:
                handle_response(chat_id, text)

        time.sleep(0.2)


if __name__ == "__main__":
    logger.info("Starting Telegram bot polling against %s", API_BASE_URL)
    poll_loop()