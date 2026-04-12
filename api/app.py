from flask import Flask, request, jsonify, g
import sqlite3
import os
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
            attending_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            consult_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            raw_input TEXT NOT NULL,
            exercise TEXT NOT NULL,
            sets INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            frequency TEXT NOT NULL,
            instructions TEXT NOT NULL,
            tips TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES Patients(patient_id) ON DELETE CASCADE
        )
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


@app.route("/patients/<int:patient_id>", methods=["GET"])
def get_patient(patient_id):
    db = get_db()
    row = db.execute("SELECT * FROM Patients WHERE patient_id = ?", (patient_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/patients/<int:patient_id>/link-telegram", methods=["POST"])
def link_telegram(patient_id):
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}
    chat_id = str(data.get("telegram_chat_id", "")).strip()

    if not chat_id:
        return jsonify({"error": "telegram_chat_id required"}), 400

    db = get_db()
    existing = db.execute("SELECT patient_id FROM Patients WHERE patient_id = ?", (patient_id,)).fetchone()
    if existing is None:
        return jsonify({"error": "Patient not found"}), 404

    db.execute("UPDATE Patients SET telegram_chat_id = ? WHERE patient_id = ?", (chat_id, patient_id))
    db.commit()

    return jsonify({"message": "Linked", "patient_id": patient_id, "telegram_chat_id": chat_id})


@app.route("/patients/by-telegram/<telegram_chat_id>", methods=["GET"])
def get_patient_by_telegram(telegram_chat_id):
    auth = require_api_key()
    if auth:
        return auth

    db = get_db()
    row = db.execute("SELECT * FROM Patients WHERE telegram_chat_id = ?", (str(telegram_chat_id),)).fetchone()
    if row is None:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/consults", methods=["POST"])
def create_consult():
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}
    required = [
        "attending_id", "patient_id", "raw_input", "exercise",
        "sets", "reps", "frequency", "instructions", "tips"
    ]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    db = get_db()
    patient = db.execute("SELECT patient_id FROM Patients WHERE patient_id = ?", (data["patient_id"],)).fetchone()
    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    cur = db.execute("""
        INSERT INTO Consults
        (attending_id, patient_id, consult_date, raw_input, exercise, sets, reps, frequency, instructions, tips)
        VALUES (?, ?, COALESCE(?, datetime('now', 'localtime')), ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(data["attending_id"]),
        int(data["patient_id"]),
        data.get("consult_date"),
        data["raw_input"],
        data["exercise"],
        int(data["sets"]),
        int(data["reps"]),
        data["frequency"],
        data["instructions"],
        data["tips"],
    ))
    db.commit()

    return jsonify({"message": "Consult created", "consult_id": cur.lastrowid}), 201


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
    rows = db.execute(
        "SELECT * FROM Consults WHERE patient_id = ? ORDER BY consult_date DESC, consult_id DESC",
        (patient_id,)
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/responses", methods=["POST"])
def create_response():
    auth = require_api_key()
    if auth:
        return auth

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json() or {}
    required = ["patient_id", "adherence", "difficulty_level", "pain_level", "progress_perception"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    db = get_db()
    patient = db.execute("SELECT patient_id FROM Patients WHERE patient_id = ?", (data["patient_id"],)).fetchone()
    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    consult_id = data.get("consult_id")
    if consult_id is not None:
        consult = db.execute("SELECT consult_id FROM Consults WHERE consult_id = ?", (consult_id,)).fetchone()
        if consult is None:
            return jsonify({"error": "Consult not found"}), 404

    cur = db.execute("""
        INSERT INTO Responses
        (patient_id, consult_id, response_date, adherence, non_compliance, difficulty_level, pain_level, progress_perception, issues, notes)
        VALUES (?, ?, COALESCE(?, datetime('now', 'localtime')), ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(data["patient_id"]),
        consult_id,
        data.get("response_date"),
        int(data["adherence"]),
        data.get("non_compliance"),
        int(data["difficulty_level"]),
        int(data["pain_level"]),
        data["progress_perception"],
        data.get("issues"),
        data.get("notes"),
    ))
    db.commit()

    return jsonify({"message": "Response created", "response_id": cur.lastrowid}), 201


@app.route("/patients/<int:patient_id>/responses/weekly", methods=["GET"])
def weekly(patient_id):
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)