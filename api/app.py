from flask import Flask, request, jsonify, g
import sqlite3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
DATABASE = os.getenv("DATABASE_PATH", "clinic.db")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY") or os.getenv("API_KEY")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def row_to_dict(row):
    return dict(row) if row else None


def require_api_key():
    if not INTERNAL_API_KEY:
        return None
    key = request.headers.get("X-API-KEY")
    if key != INTERNAL_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    db.execute("""
    CREATE TABLE IF NOT EXISTS Patients (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        telegram_chat_id TEXT
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS Consults (
    consult_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    patient_name TEXT NOT NULL,
    attending_name TEXT NOT NULL,
    consult_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    raw_attending_instructions TEXT,
    ai_attending_instructions TEXT,
    additional_attending_instructions TEXT,
    FOREIGN KEY (patient_id) REFERENCES Patients(patient_id) ON DELETE CASCADE
    );
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS Responses (
        response_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        consult_id INTEGER,
        response_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        adherence INTEGER NOT NULL CHECK (adherence BETWEEN 1 AND 5),
        non_compliance TEXT,
        difficulty_level INTEGER NOT NULL CHECK (difficulty_level BETWEEN 1 AND 5),
        pain_level INTEGER NOT NULL CHECK (pain_level BETWEEN 0 AND 10),
        progress_perception TEXT NOT NULL,
        issues TEXT,
        notes TEXT,
        FOREIGN KEY (patient_id) REFERENCES Patients(patient_id) ON DELETE CASCADE,
        FOREIGN KEY (consult_id) REFERENCES Consults(consult_id) ON DELETE SET NULL
    )
    """)

    db.commit()
    db.close()


init_db()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/patients", methods=["GET"])
def get_patients():
    db = get_db()
    rows = db.execute("SELECT * FROM Patients ORDER BY patient_id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/patients/<int:patient_id>", methods=["GET"])
def get_patient(patient_id):
    db = get_db()
    row = db.execute("SELECT * FROM Patients WHERE patient_id = ?", (patient_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/patients", methods=["POST"])
def create_patient():
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}
    patient_name = str(data.get("patient_name", "")).strip()
    telegram_chat_id = str(data.get("telegram_chat_id", "")).strip() or None

    if not patient_name:
        return jsonify({"error": "patient_name is required"}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO Patients (patient_name, telegram_chat_id) VALUES (?, ?)",
        (patient_name, telegram_chat_id)
    )
    db.commit()

    return jsonify({"message": "Patient created", "patient_id": cur.lastrowid}), 201


@app.route("/patients/<int:patient_id>/link-telegram", methods=["PATCH", "POST"])
def link_telegram(patient_id):
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}
    chat_id = str(data.get("telegram_chat_id", "")).strip() or None

    db = get_db()
    existing = db.execute(
        "SELECT patient_id FROM Patients WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()

    if existing is None:
        return jsonify({"error": "Patient not found"}), 404

    db.execute(
        "UPDATE Patients SET telegram_chat_id = ? WHERE patient_id = ?",
        (chat_id, patient_id)
    )
    db.commit()

    return jsonify({
        "message": "Telegram chat updated",
        "patient_id": patient_id,
        "telegram_chat_id": chat_id
    })


@app.route("/patients/by-telegram/<telegram_chat_id>", methods=["GET"])
def get_patient_by_telegram(telegram_chat_id):
    auth = require_api_key()
    if auth:
        return auth

    db = get_db()
    row = db.execute(
        "SELECT * FROM Patients WHERE telegram_chat_id = ?",
        (str(telegram_chat_id),)
    ).fetchone()

    if row is None:
        return jsonify({"error": "Patient not found"}), 404

    return jsonify(row_to_dict(row))


@app.route("/consults", methods=["GET"])
def get_all_consults():
    auth = require_api_key()
    if auth:
        return auth

    db = get_db()
    rows = db.execute("""
        SELECT * FROM Consults
        ORDER BY consult_date DESC, consult_id DESC
    """).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/consults", methods=["POST"])
def create_consult():
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}

    # Required fields
    patient_id = data.get("patient_id")
    attending_name = data.get("attending_name")

    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400
    if not attending_name or not str(attending_name).strip():
        return jsonify({"error": "attending_name is required"}), 400

    db = get_db()

    # Load patient_name from Patients table
    patient = db.execute(
        "SELECT patient_id, patient_name FROM Patients WHERE patient_id = ?",
        (int(patient_id),),
    ).fetchone()

    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    patient_name = patient["patient_name"]

    raw_instr = data.get("raw_attending_instructions")
    ai_instr = data.get("ai_attending_instructions")
    add_instr = data.get("additional_attending_instructions")
    consult_date = data.get("consult_date")  # optional

    cur = db.execute(
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
        VALUES (?, ?, ?, COALESCE(?, datetime('now', 'localtime')), ?, ?, ?)
        """,
        (
            int(patient_id),
            patient_name,
            str(attending_name).strip(),
            consult_date,
            (str(raw_instr).strip() if raw_instr is not None else None),
            (str(ai_instr).strip() if ai_instr is not None else None),
            (str(add_instr).strip() if add_instr is not None else None),
        ),
    )
    db.commit()

    return jsonify(
        {
            "message": "Consult created",
            "consult_id": cur.lastrowid,
        }
    ), 201


@app.route("/consults/<int:consult_id>", methods=["GET"])
def get_consult(consult_id):
    db = get_db()
    row = db.execute("SELECT * FROM Consults WHERE consult_id = ?", (consult_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Consult not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/patients/<int:patient_id>/consults", methods=["GET"])
def get_patient_consults(patient_id):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM Consults
        WHERE patient_id = ?
        ORDER BY consult_date DESC, consult_id DESC
    """, (patient_id,)).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/consults/<int:consult_id>/instructions", methods=["PATCH"])
def update_consult_instructions(consult_id):
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}

    # Allow partial update – at least one of the 3 keys should be present
    keys = {
        "raw_attending_instructions": "raw_attending_instructions",
        "ai_attending_instructions": "ai_attending_instructions",
        "additional_attending_instructions": "additional_attending_instructions",
    }

    fields_to_update = {}
    for body_key, column_name in keys.items():
        if body_key in data:
            val = data.get(body_key)
            # allow explicit null to clear field
            fields_to_update[column_name] = (
                None if val is None else str(val).strip()
            )

    if not fields_to_update:
        return jsonify(
            {
                "error": "At least one of "
                "raw_attending_instructions, "
                "ai_attending_instructions, "
                "additional_attending_instructions must be provided"
            }
        ), 400

    db = get_db()

    existing = db.execute(
        "SELECT consult_id FROM Consults WHERE consult_id = ?",
        (consult_id,),
    ).fetchone()
    if existing is None:
        return jsonify({"error": "Consult not found"}), 404

    # Build dynamic UPDATE query
    set_clause = ", ".join(f"{col} = ?" for col in fields_to_update.keys())
    values = list(fields_to_update.values())
    values.append(consult_id)

    db.execute(
        f"UPDATE Consults SET {set_clause} WHERE consult_id = ?",
        tuple(values),
    )
    db.commit()

    row = db.execute(
        "SELECT * FROM Consults WHERE consult_id = ?",
        (consult_id,),
    ).fetchone()

    return jsonify(
        {
            "message": "Consult instructions updated",
            "consult": row_to_dict(row),
        }
    )


@app.route("/responses", methods=["POST"])
def create_response():
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}
    required = ["patient_id", "adherence", "difficulty_level", "pain_level", "progress_perception"]
    missing = [k for k in required if data.get(k) in (None, "")]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    db = get_db()
    patient = db.execute(
        "SELECT patient_id FROM Patients WHERE patient_id = ?",
        (int(data["patient_id"]),)
    ).fetchone()
    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    consult_id = data.get("consult_id")
    if consult_id is not None:
        consult = db.execute(
            "SELECT consult_id FROM Consults WHERE consult_id = ?",
            (consult_id,)
        ).fetchone()
        if consult is None:
            return jsonify({"error": "Consult not found"}), 404

    cur = db.execute("""
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
        VALUES (?, ?, COALESCE(?, datetime('now', 'localtime')), ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(data["patient_id"]),
        consult_id,
        data.get("response_date"),
        int(data["adherence"]),
        data.get("non_compliance"),
        int(data["difficulty_level"]),
        int(data["pain_level"]),
        str(data["progress_perception"]).strip(),
        data.get("issues"),
        data.get("notes"),
    ))
    db.commit()

    return jsonify({"message": "Response created", "response_id": cur.lastrowid}), 201


@app.route("/responses", methods=["GET"])
def get_all_responses():
    auth = require_api_key()
    if auth:
        return auth

    db = get_db()
    rows = db.execute("""
        SELECT * FROM Responses
        ORDER BY response_date DESC, response_id DESC
    """).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/patients/<int:patient_id>/responses", methods=["GET"])
def get_patient_responses(patient_id):
    auth = require_api_key()
    if auth:
        return auth

    db = get_db()
    patient = db.execute(
        "SELECT patient_id FROM Patients WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()
    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    rows = db.execute("""
        SELECT * FROM Responses
        WHERE patient_id = ?
        ORDER BY response_date DESC, response_id DESC
    """, (patient_id,)).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route("/patients/<int:patient_id>/responses/weekly", methods=["GET"])
def get_patient_responses_weekly(patient_id):
    auth = require_api_key()
    if auth:
        return auth

    db = get_db()
    rows = db.execute("""
        SELECT * FROM Responses
        WHERE patient_id = ?
          AND response_date >= datetime('now', '-7 days')
        ORDER BY response_date DESC, response_id DESC
    """, (patient_id,)).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route("/patients/<int:patient_id>/responses/by-week", methods=["GET"])
def get_patient_responses_by_week(patient_id):
    auth = require_api_key()
    if auth:
        return auth

    end_date_str = request.args.get("end_date", "").strip()
    if not end_date_str:
        return jsonify({"error": "end_date query param is required in YYYY-MM-DD format"}), 400

    end_date = parse_date(end_date_str)
    if not end_date:
        return jsonify({"error": "Invalid end_date. Use YYYY-MM-DD"}), 400

    start_date = end_date - timedelta(days=6)
    start_date_str = start_date.strftime("%Y-%m-%d 00:00:00")
    end_date_full_str = end_date.strftime("%Y-%m-%d 23:59:59")

    db = get_db()
    rows = db.execute("""
        SELECT * FROM Responses
        WHERE patient_id = ?
          AND response_date >= ?
          AND response_date <= ?
        ORDER BY response_date DESC, response_id DESC
    """, (patient_id, start_date_str, end_date_full_str)).fetchall()

    return jsonify({
        "patient_id": patient_id,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "responses": [row_to_dict(r) for r in rows]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
