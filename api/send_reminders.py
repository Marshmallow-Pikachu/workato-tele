import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
API_KEY = os.getenv("API_KEY") or os.getenv("INTERNAL_API_KEY")


def tg_send(chat_id, text):
    if not BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=20,
    )

    if not r.ok:
        raise RuntimeError(
            f"Telegram send failed: status={r.status_code}, body={r.text}"
        )

    return r.json()


def api_get(path):
    headers = {}
    if API_KEY:
        headers["X-API-KEY"] = API_KEY
    url = API_BASE_URL.rstrip("/") + path
    return requests.get(url, headers=headers, timeout=20)


def get_patient(patient_id):
    resp = api_get(f"/patients/{patient_id}")
    resp.raise_for_status()
    return resp.json()


def get_consult_for_patient(patient_id, consult_id=None):
    if consult_id is not None:
        resp = api_get(f"/consults/{consult_id}")
        resp.raise_for_status()
        consult = resp.json()

        if int(consult["patient_id"]) != int(patient_id):
            raise RuntimeError(
                f"Consult {consult_id} does not belong to patient {patient_id}"
            )
        return consult

    c_resp = api_get(f"/patients/{patient_id}/consults")
    c_resp.raise_for_status()
    consults = c_resp.json()
    if not consults:
        raise RuntimeError(f"Patient {patient_id} has no consults")
    return consults[0]


def build_instruction_message(patient, consult):
    ai_instr = (consult.get("ai_attending_instructions") or "").strip()
    add_instr = (consult.get("additional_attending_instructions") or "").strip()
    attending_name = consult.get("attending_name") or "your therapist"
    consult_id = consult.get("consult_id")

    if not ai_instr and not add_instr:
        raise RuntimeError(f"Consult {consult_id} has no instructions to send")

    lines = [
        f"Hi {patient.get('patient_name', '')}, here are your exercise instructions from {attending_name}:",
        f"Consult ID: {consult_id}",
    ]

    if ai_instr:
        lines.extend(["", "AI-assisted summary:", ai_instr])

    if add_instr:
        lines.extend(["", "Additional notes:", add_instr])

    return "\n".join(lines)


def send_response_reminders():
    resp = api_get("/patients")
    resp.raise_for_status()
    patients = resp.json()

    for p in patients:
        chat_id = p.get("telegram_chat_id")
        if not chat_id:
            continue

        try:
            tg_send(
                chat_id,
                f"Hi {p.get('patient_name', '')}, it's time to submit your weekly exercise response.\n\n"
                "Please reply with:\n"
                "weekly\n\n"
                "I will then guide you through a few short questions."
            )
        except RuntimeError as exc:
            print(f"Something went wrong when sending reminder to patient {p.get('patient_id')}: {exc}")


def send_one_response_reminders(patient_id, consult_id=None):
    p = get_patient(patient_id)

    chat_id = p.get("telegram_chat_id")
    if not chat_id:
        raise RuntimeError(f"Patient {patient_id} has no telegram_chat_id")

    consult_suffix = f" {consult_id}" if consult_id is not None else ""
    try:
        tg_send(
            chat_id,
            f"Hi {p.get('patient_name', '')}, it's time to submit your weekly exercise response.\n\n"
            "Please reply with:\n"
            f"weekly{consult_suffix}\n\n"
            "I will then guide you through a few short questions."
        )
    except RuntimeError as exc:
        print(f"Something went wrong when sending reminder to patient {patient_id}: {exc}")
        raise


def send_latest_instructions():
    resp = api_get("/patients")
    resp.raise_for_status()
    patients = resp.json()

    for p in patients:
        chat_id = p.get("telegram_chat_id")
        patient_id = p.get("patient_id")

        if not chat_id or not patient_id:
            continue

        try:
            consult = get_consult_for_patient(patient_id)
            msg = build_instruction_message(p, consult)
            tg_send(chat_id, msg)
        except Exception as exc:
            print(f"Skipping patient {patient_id}: {exc}")


def send_one_instructions(patient_id, consult_id=None):
    p = get_patient(patient_id)

    chat_id = p.get("telegram_chat_id")
    if not chat_id:
        raise RuntimeError(f"Patient {patient_id} has no telegram_chat_id")

    consult = get_consult_for_patient(patient_id, consult_id=consult_id)
    msg = build_instruction_message(p, consult)
    tg_send(chat_id, msg)


def send_one_latest_instructions(patient_id):
    send_one_instructions(patient_id, consult_id=None)


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    send_latest_instructions()