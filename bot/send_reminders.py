import os
import requests
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
API_KEY = os.getenv("API_KEY")


def tg_send(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    r.raise_for_status()


def api_get(path):
    headers = {}
    if API_KEY:
        headers["X-API-KEY"] = API_KEY
    url = API_BASE_URL.rstrip("/") + path
    return requests.get(url, headers=headers, timeout=20)


def main():
    resp = api_get("/patients")
    resp.raise_for_status()
    patients = resp.json()

    for p in patients:
        chat_id = p.get("telegram_chat_id")
        if not chat_id:
            continue

        tg_send(chat_id, (
            f"Hi {p.get('patient_name','')}, reminder to submit your exercise response today.\n\n"
            "Reply in this format:\n"
            "adherence: 1-5\n"
            "difficulty_level: 1-5\n"
            "pain_level: 0-10\n"
            "progress_perception: Better/Same/Worse\n"
            "non_compliance: (optional)\n"
            "issues: (optional)\n"
            "notes: (optional)"
        ))


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    main()
