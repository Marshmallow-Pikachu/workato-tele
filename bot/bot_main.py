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
weekly_sessions = {}

QUESTION_FLOW = [
    (
        "adherence",
        "Question 1/6:\nOut of the past 7 days, on how many days did you complete your exercises?\nReply with a whole number from 0 to 7."
    ),
    (
        "difficulty_level",
        "Question 2/6:\nOn a scale of 1 to 5, how difficult were the exercises this week?"
    ),
    (
        "pain_level",
        "Question 3/6:\nOn a scale of 0 to 10, how much pain did you feel during or after the exercises this week?"
    ),
    (
        "progress_perception",
        "Question 4/6:\nHow would you describe your progress this week?\nReply with one of: Better, Slightly better, Same, Worse"
    ),
    (
        "issues",
        "Question 5/6:\nDid you face any issues while doing the exercises?\nReply 'none' if not applicable."
    ),
    (
        "notes",
        "Question 6/6:\nAny other notes you want to share?\nReply 'none' if not applicable."
    ),
]

NON_COMPLIANCE_QUESTION = (
    "You mentioned that you completed the exercises on fewer than 3 days this week.\n"
    "Please briefly describe why you missed or skipped them."
)


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
        if len(text) > 3500:
            text = text[:3500] + "\n\n[Message truncated]"
        tg("sendMessage", {"chat_id": chat_id, "text": text})
    except RequestException as exc:
        logger.exception("Failed to send Telegram message to chat_id=%s: %s", chat_id, exc)


def normalize_optional_text(value):
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.lower() in {"none", "n/a", "na", "-"}:
        return None
    return cleaned


def validate_consult_for_patient(patient_id, consult_id):
    resp = api("GET", f"/consults/{consult_id}")
    if resp.status_code != 200:
        return False, f"Consult {consult_id} was not found."

    consult = resp.json()
    if int(consult["patient_id"]) != int(patient_id):
        return False, f"Consult {consult_id} does not belong to your patient record."

    return True, None


def handle_start(chat_id, username, text):
    m = re.match(r"^/start\s+(\d+)$", text.strip())
    if not m:
        safe_send(
            chat_id,
            "Hi! To link you to a patient record, send:\n/start <patient_id>\n\nExample: /start 3",
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
        safe_send(
            chat_id,
            "Linking failed because the clinic server could not be reached. Please try again shortly."
        )
        return

    if resp.status_code == 200:
        safe_send(
            chat_id,
            f"Linked to patient_id={patient_id}. You can now submit weekly responses by replying:\nweekly\n\n"
            "If your clinic gives you a consult ID, you can also reply like:\nweekly 12"
        )
    else:
        safe_send(chat_id, f"Linking failed: {resp.status_code} {resp.text}")


def start_weekly_questionnaire(chat_id, patient_id, consult_id=None):
    weekly_sessions[str(chat_id)] = {
        "patient_id": patient_id,
        "consult_id": consult_id,
        "step_index": 0,
        "answers": {},
        "awaiting_non_compliance": False,
    }

    intro = "Let's submit your weekly exercise response."
    if consult_id is not None:
        intro += f"\nThis response will be saved for consult_id={consult_id}."

    safe_send(chat_id, intro + "\n\n" + QUESTION_FLOW[0][1])


def handle_weekly_response(chat_id, text):
    session_data = weekly_sessions.get(str(chat_id))
    if not session_data:
        return False

    value = text.strip()

    if session_data.get("awaiting_non_compliance"):
        session_data["answers"]["non_compliance"] = normalize_optional_text(value)
        session_data["awaiting_non_compliance"] = False
        next_question = QUESTION_FLOW[session_data["step_index"]][1]
        safe_send(chat_id, next_question)
        return True

    step_index = session_data["step_index"]
    field_name, _ = QUESTION_FLOW[step_index]

    try:
        if field_name == "adherence":
            parsed = int(value)
            if parsed < 0 or parsed > 7:
                raise ValueError
            session_data["answers"][field_name] = parsed
            session_data["step_index"] += 1

            if parsed < 3:
                session_data["awaiting_non_compliance"] = True
                safe_send(chat_id, NON_COMPLIANCE_QUESTION)
                return True

        elif field_name == "difficulty_level":
            parsed = int(value)
            if parsed < 1 or parsed > 5:
                raise ValueError
            session_data["answers"][field_name] = parsed
            session_data["step_index"] += 1

        elif field_name == "pain_level":
            parsed = int(value)
            if parsed < 0 or parsed > 10:
                raise ValueError
            session_data["answers"][field_name] = parsed
            session_data["step_index"] += 1

        elif field_name == "progress_perception":
            allowed = {"better", "slightly better", "same", "worse"}
            if value.lower() not in allowed:
                safe_send(chat_id, "Please reply with one of: Better, Slightly better, Same, Worse")
                return True
            session_data["answers"][field_name] = value
            session_data["step_index"] += 1

        elif field_name in ("issues", "notes"):
            session_data["answers"][field_name] = normalize_optional_text(value)
            session_data["step_index"] += 1

    except ValueError:
        if field_name == "adherence":
            safe_send(chat_id, "Please reply with a whole number from 0 to 7.")
        elif field_name == "difficulty_level":
            safe_send(chat_id, "Please reply with a whole number from 1 to 5.")
        elif field_name == "pain_level":
            safe_send(chat_id, "Please reply with a whole number from 0 to 10.")
        return True

    if session_data["step_index"] >= len(QUESTION_FLOW):
        payload = {
            "patient_id": session_data["patient_id"],
            "consult_id": session_data.get("consult_id"),
            "adherence": session_data["answers"]["adherence"],
            "difficulty_level": session_data["answers"]["difficulty_level"],
            "pain_level": session_data["answers"]["pain_level"],
            "progress_perception": session_data["answers"]["progress_perception"],
            "non_compliance": session_data["answers"].get("non_compliance"),
            "issues": session_data["answers"].get("issues"),
            "notes": session_data["answers"].get("notes"),
        }

        try:
            resp = api("POST", "/responses", payload)
        except RequestException as exc:
            logger.exception("API save failed for patient_id=%s: %s", session_data["patient_id"], exc)
            safe_send(
                chat_id,
                "Failed to save because the clinic server could not be reached. Please try again shortly."
            )
            weekly_sessions.pop(str(chat_id), None)
            return True

        if resp.status_code == 201:
            safe_send(chat_id, "Saved — thank you! Your weekly response has been submitted.")
        else:
            safe_send(chat_id, f"Failed to save: {resp.status_code} {resp.text}")

        weekly_sessions.pop(str(chat_id), None)
        return True

    next_question = QUESTION_FLOW[session_data["step_index"]][1]
    safe_send(chat_id, next_question)
    return True


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
    clean_text = text.strip()

    weekly_match = re.match(r"^weekly(?:\s+(\d+))?$", clean_text.lower())
    if weekly_match:
        consult_id = int(weekly_match.group(1)) if weekly_match.group(1) else None

        if consult_id is not None:
            ok, error_msg = validate_consult_for_patient(patient_id, consult_id)
            if not ok:
                safe_send(chat_id, error_msg)
                return

        start_weekly_questionnaire(chat_id, patient_id, consult_id=consult_id)
        return

    if handle_weekly_response(chat_id, clean_text):
        return

    safe_send(
        chat_id,
        "To submit your weekly response, reply with:\nweekly\n\n"
        "Or, for a specific consult:\nweekly <consult_id>"
    )


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