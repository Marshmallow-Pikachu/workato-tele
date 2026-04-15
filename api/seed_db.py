import os
import sqlite3
from datetime import datetime, timedelta
from random import randint, choice, random
from dotenv import load_dotenv

load_dotenv()

DATABASE = os.getenv("DATABASE_PATH", "clinic.db")

PATIENT_NAMES = [
    "Alice Tan",
    "Bob Lee",
    "Charlie Ng",
    "Darren Khoo",
    "Elaine Lim",
    "Farah Rahman",
    "Gavin Chua",
    "Hazel Wong",
    "Ivan Goh",
    "Jasmine Teo",
]

ATTENDING_NAMES = [
    "Dr Lim",
    "Dr Chen",
    "Dr Kumar",
    "Dr Wong",
]

RAW_INSTRUCTIONS = [
    "Initial assessment, prescribe knee flexion exercises.",
    "Lower back pain, prescribe core stability exercises.",
    "Shoulder impingement, advise mobility and rotator cuff strengthening.",
    "Post-op ACL rehab, focus on quad activation.",
    "Ankle sprain, start with balance and proprioception drills.",
    "Neck pain, recommend posture corrections and isometric exercises.",
]

PROGRESS_PHRASES = ["Better", "Slightly better", "Same", "Worse"]
ISSUE_PHRASES = [
    "Mild stiffness in the morning.",
    "Back feels tight after sitting.",
    "Unsure about correct form.",
    "Pain after prolonged walking.",
    "Fatigue after exercises.",
]


def main():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    now = datetime.now()

    # --- Patients (10) ---
    patients = []
    for i, name in enumerate(PATIENT_NAMES, start=1):
        # Give first few patients telegram IDs, others None
        tg_id = str(100000 + i) if i <= 6 else None
        patients.append((name, tg_id))

    cur.executemany(
        """
        INSERT INTO Patients (patient_name, telegram_chat_id)
        VALUES (?, ?)
        """,
        patients,
    )
    conn.commit()

    cur.execute("SELECT patient_id, patient_name FROM Patients ORDER BY patient_id")
    patient_rows = cur.fetchall()
    print("Seeded patients:")
    for p in patient_rows:
        print("  ", dict(p))

    # --- Consults (20) ---
    consults = []
    for _ in range(20):
        patient_row = choice(patient_rows)
        patient_id = patient_row["patient_id"]
        patient_name = patient_row["patient_name"]
        attending_name = choice(ATTENDING_NAMES)

        # Random date in the last 30 days
        days_ago = randint(0, 29)
        c_date = now - timedelta(days=days_ago)
        consult_date_str = c_date.strftime("%Y-%m-%d %H:%M:%S")

        raw = choice(RAW_INSTRUCTIONS)
        ai_instr = None
        add_instr = None

        # ~40% have AI instructions, ~30% have additional instructions
        if random() < 0.4:
            ai_instr = f"AI summary: {raw[:50]}..."
        if random() < 0.3:
            add_instr = "Additional advice: avoid high-impact activities for a week."

        consults.append(
            (
                patient_id,
                patient_name,
                attending_name,
                consult_date_str,
                raw,
                ai_instr,
                add_instr,
            )
        )

    cur.executemany(
        """
        INSERT INTO Consults (
            patient_id,
            patient_name,
            attending_name,
            consult_date,
            raw_attending_instructions,
            ai_attending_instructions,
            additional_attending_instructions
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        consults,
    )
    conn.commit()

    cur.execute(
        "SELECT consult_id, patient_id, patient_name, consult_date "
        "FROM Consults ORDER BY consult_id"
    )
    consult_rows = cur.fetchall()
    print("\nSeeded consults:")
    for c in consult_rows[:5]:
        print("  ", dict(c))
    if len(consult_rows) > 5:
        print(f"  ... ({len(consult_rows)} total)")

    consult_ids = [c["consult_id"] for c in consult_rows]

    # --- Responses (70) ---
    responses = []
    for _ in range(70):
        # Random patient
        p_row = choice(patient_rows)
        patient_id = p_row["patient_id"]

        # Randomly tie to a consult (or not)
        if random() < 0.8 and consult_ids:
            c_row = choice(consult_rows)
            consult_id = c_row["consult_id"]
            base_date = datetime.strptime(
                c_row["consult_date"], "%Y-%m-%d %H:%M:%S"
            )
            # Response up to 10 days after consult
            r_days = randint(0, 10)
            r_date = base_date + timedelta(days=r_days)
        else:
            consult_id = None
            # Random date in last 30 days
            r_days = randint(0, 29)
            r_date = now - timedelta(days=r_days)

        response_date_str = r_date.strftime("%Y-%m-%d %H:%M:%S")

        adherence = randint(1, 5)
        difficulty = randint(1, 5)
        pain = randint(0, 10)
        progress = choice(PROGRESS_PHRASES)

        non_compliance = None
        if random() < 0.5:
            non_compliance = choice(
                [
                    "Missed one session.",
                    "Skipped weekend exercises.",
                    "Forgot instructions.",
                ]
            )

        issues = None
        if random() < 0.6:
            issues = choice(ISSUE_PHRASES)

        notes = None
        if random() < 0.4:
            notes = choice(
                [
                    "Feels improved overall.",
                    "Wants to discuss progression next visit.",
                    "Motivation is good.",
                    "Needs clarification on one exercise.",
                ]
            )

        responses.append(
            (
                patient_id,
                consult_id,
                response_date_str,
                adherence,
                non_compliance,
                difficulty,
                pain,
                progress,
                issues,
                notes,
            )
        )

    cur.executemany(
        """
        INSERT INTO Responses (
            patient_id,
            consult_id,
            response_date,
            adherence,
            non_compliance,
            difficulty_level,
            pain_level,
            progress_perception,
            issues,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        responses,
    )
    conn.commit()

    cur.execute(
        "SELECT response_id, patient_id, consult_id, response_date "
        "FROM Responses ORDER BY response_id"
    )
    response_rows = cur.fetchall()
    print("\nSeeded responses:")
    for r in response_rows[:5]:
        print("  ", dict(r))
    if len(response_rows) > 5:
        print(f"  ... ({len(response_rows)} total)")

    conn.close()
    print(
        "\nSeeding complete: "
        f"{len(patient_rows)} patients, {len(consult_rows)} consults, {len(response_rows)} responses."
    )


if __name__ == "__main__":
    main()