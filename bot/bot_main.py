import os
import time
import re
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
API_KEY = os.getenv("API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")


def tg(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def api(method, path, json_body=None):
    url = API_BASE_URL.rstrip("/") + path
    headers = {}
    if API_KEY:
        headers["X-API-KEY"] = API_KEY
    r = requests.request(method, url, json=json_body, headers=headers, timeout=20)
    return r


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
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": "Hi! To link you to a patient record, send: /start <patient_id>\nExample: /start 3"
        })
        return

    patient_id = int(m.group(1))
    resp = api("POST", f"/patients/{patient_id}/link-telegram", {
        "telegram_chat_id": str(chat_id),
        "telegram_username": username
    })

    if resp.status_code == 200:
        tg("sendMessage", {"chat_id": chat_id, "text": f"Linked to patient_id={patient_id}. You can now submit responses."})
    else:
        tg("sendMessage", {"chat_id": chat_id, "text": f"Linking failed: {resp.status_code} {resp.text}"})


def handle_response(chat_id, text):
    lookup = api("GET", f"/patients/by-telegram/{chat_id}")
    if lookup.status_code != 200:
        tg("sendMessage", {"chat_id": chat_id, "text": "You're not linked yet. Send: /start <patient_id>"})
        return

    patient = lookup.json()
    patient_id = patient["patient_id"]

    kv = parse_kv(text)
    required = ["adherence", "difficulty_level", "pain_level", "progress_perception"]
    if not all(k in kv and kv[k] for k in required):
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": "Invalid format. Reply like:\n"
                    "adherence: 4\n"
                    "difficulty_level: 2\n"
                    "pain_level: 1\n"
                    "progress_perception: Better\n"
                    "non_compliance: (optional)\n"
                    "issues: (optional)\n"
                    "notes: (optional)"
        })
        return

    payload = {
        "patient_id": patient_id,
        "adherence": int(kv["adherence"]),
        "difficulty_level": int(kv["difficulty_level"]),
        "pain_level": int(kv["pain_level"]),
        "progress_perception": kv["progress_perception"],
        "non_compliance": kv.get("non_compliance") or None,
        "issues": kv.get("issues") or None,
        "notes": kv.get("notes") or None
    }

    resp = api("POST", "/responses", payload)
    if resp.status_code == 201:
        tg("sendMessage", {"chat_id": chat_id, "text": "Saved — thank you!"})
    else:
        tg("sendMessage", {"chat_id": chat_id, "text": f"Failed to save: {resp.status_code} {resp.text}"})


def poll_loop():
    offset = None
    while True:
        payload = {"timeout": 30}
        if offset is not None:
            payload["offset"] = offset

        updates = tg("getUpdates", payload)
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

            if text.strip().startswith("/start"):
                handle_start(chat_id, username, text)
            else:
                handle_response(chat_id, text)

        time.sleep(0.2)


if __name__ == "__main__":
    poll_loop()
