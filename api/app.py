from flask import Flask, request, jsonify, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = os.getenv("DATABASE_PATH", "clinic.db")
API_KEY = os.getenv("API_KEY")


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
    if not API_KEY:
        return None
    key = request.headers.get("X-API-KEY")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    db.execute("""
        CREATE TABLE IF NOT EXISTS Patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            raw_input TEXT NOT NULL,
            exercise TEXT NOT NULL,
            sets INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            frequency TEXT NOT NULL,
            instructions TEXT NOT NULL,
            tips TEXT NOT NULL,
            telegram_chat_id TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS Responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            response_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            adherence INTEGER NOT NULL CHECK (adherence BETWEEN 1 AND 5),
            non_compliance TEXT,
            difficulty_level INTEGER NOT NULL CHECK (difficulty_level BETWEEN 1 AND 5),
            pain_level INTEGER NOT NULL CHECK (pain_level BETWEEN 0 AND 10),
            progress_perception TEXT NOT NULL,
            issues TEXT,
            notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES Patients(patient_id) ON DELETE CASCADE
        )
    """)

    cols = [r[1] for r in db.execute("PRAGMA table_info(Patients)").fetchall()]
    if "telegram_chat_id" not in cols:
        db.execute("ALTER TABLE Patients ADD COLUMN telegram_chat_id TEXT")

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


@app.route("/patients/<int:patient_id>/link-telegram", methods=["POST"])
def link_telegram(patient_id):
    auth = require_api_key()
    if auth:
        return auth

    data = request.get_json() or {}
    chat_id = str(data.get("telegram_chat_id", "")).strip()
    username = str(data.get("telegram_username", "")).strip() or None

    if not chat_id:
        return jsonify({"error": "telegram_chat_id required"}), 400

    db = get_db()
    existing = db.execute("SELECT patient_id FROM Patients WHERE patient_id = ?", (patient_id,)).fetchone()
    if existing is None:
        return jsonify({"error": "Patient not found"}), 404

    db.execute("UPDATE Patients SET telegram_chat_id = ? WHERE patient_id = ?", (chat_id, patient_id))
    db.commit()

    return jsonify({"message": "Linked", "patient_id": patient_id, "telegram_chat_id": chat_id, "telegram_username": username})


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


@app.route("/responses", methods=["POST"])
def create_response():
    auth = require_api_key()
    if auth:
        return auth

    data = request.get_json() or {}
    required = ["patient_id", "adherence", "difficulty_level", "pain_level", "progress_perception"]
    for k in required:
        if k not in data:
            return jsonify({"error": f"Missing field: {k}"}), 400

    db = get_db()
    patient = db.execute("SELECT patient_id FROM Patients WHERE patient_id = ?", (data["patient_id"],)).fetchone()
    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    cur = db.execute("""
        INSERT INTO Responses
        (patient_id, response_date, adherence, non_compliance, difficulty_level, pain_level, progress_perception, issues, notes)
        VALUES (?, COALESCE(?, datetime('now', 'localtime')), ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["patient_id"],
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
