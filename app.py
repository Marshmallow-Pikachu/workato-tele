from flask import Flask, request, jsonify, g
import sqlite3

app = Flask(__name__)
DATABASE = "clinic.db"


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
            tips TEXT NOT NULL
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

    db.commit()
    db.close()


init_db()


# -------------------------
# Patients CRUD
# -------------------------

@app.route("/patients", methods=["POST"])
def create_patient():
    data = request.get_json()

    required_fields = [
        "patient_name", "raw_input", "exercise", "sets", "reps",
        "frequency", "instructions", "tips"
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()
    cur = db.execute("""
        INSERT INTO Patients
        (patient_name, raw_input, exercise, sets, reps, frequency, instructions, tips)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["patient_name"],
        data["raw_input"],
        data["exercise"],
        data["sets"],
        data["reps"],
        data["frequency"],
        data["instructions"],
        data["tips"]
    ))
    db.commit()

    return jsonify({
        "message": "Patient created",
        "patient_id": cur.lastrowid
    }), 201


@app.route("/patients", methods=["GET"])
def get_patients():
    db = get_db()
    rows = db.execute("SELECT * FROM Patients ORDER BY patient_id DESC").fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.route("/patients/<int:patient_id>", methods=["GET"])
def get_patient(patient_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM Patients WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()

    if row is None:
        return jsonify({"error": "Patient not found"}), 404

    return jsonify(row_to_dict(row))


@app.route("/patients/<int:patient_id>", methods=["PUT"])
def update_patient(patient_id):
    data = request.get_json()
    db = get_db()

    existing = db.execute(
        "SELECT * FROM Patients WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()

    if existing is None:
        return jsonify({"error": "Patient not found"}), 404

    updated_values = {
        "patient_name": data.get("patient_name", existing["patient_name"]),
        "raw_input": data.get("raw_input", existing["raw_input"]),
        "exercise": data.get("exercise", existing["exercise"]),
        "sets": data.get("sets", existing["sets"]),
        "reps": data.get("reps", existing["reps"]),
        "frequency": data.get("frequency", existing["frequency"]),
        "instructions": data.get("instructions", existing["instructions"]),
        "tips": data.get("tips", existing["tips"]),
    }

    db.execute("""
        UPDATE Patients
        SET patient_name = ?, raw_input = ?, exercise = ?, sets = ?, reps = ?,
            frequency = ?, instructions = ?, tips = ?
        WHERE patient_id = ?
    """, (
        updated_values["patient_name"],
        updated_values["raw_input"],
        updated_values["exercise"],
        updated_values["sets"],
        updated_values["reps"],
        updated_values["frequency"],
        updated_values["instructions"],
        updated_values["tips"],
        patient_id
    ))
    db.commit()

    return jsonify({"message": "Patient updated"})


@app.route("/patients/<int:patient_id>", methods=["DELETE"])
def delete_patient(patient_id):
    db = get_db()
    cur = db.execute("DELETE FROM Patients WHERE patient_id = ?", (patient_id,))
    db.commit()

    if cur.rowcount == 0:
        return jsonify({"error": "Patient not found"}), 404

    return jsonify({"message": "Patient deleted"})


# -------------------------
# Responses CRUD
# -------------------------

@app.route("/responses", methods=["POST"])
def create_response():
    data = request.get_json()

    required_fields = [
        "patient_id", "adherence", "difficulty_level",
        "pain_level", "progress_perception"
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()

    patient = db.execute(
        "SELECT patient_id FROM Patients WHERE patient_id = ?",
        (data["patient_id"],)
    ).fetchone()

    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    cur = db.execute("""
        INSERT INTO Responses
        (patient_id, response_date, adherence, non_compliance, difficulty_level,
         pain_level, progress_perception, issues, notes)
        VALUES (?, COALESCE(?, datetime('now', 'localtime')), ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["patient_id"],
        data.get("response_date"),
        data["adherence"],
        data.get("non_compliance"),
        data["difficulty_level"],
        data["pain_level"],
        data["progress_perception"],
        data.get("issues"),
        data.get("notes")
    ))
    db.commit()

    return jsonify({
        "message": "Response created",
        "response_id": cur.lastrowid
    }), 201


@app.route("/responses", methods=["GET"])
def get_responses():
    db = get_db()
    rows = db.execute("""
        SELECT * FROM Responses
        ORDER BY response_date DESC, response_id DESC
    """).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.route("/responses/<int:response_id>", methods=["GET"])
def get_response(response_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM Responses WHERE response_id = ?",
        (response_id,)
    ).fetchone()

    if row is None:
        return jsonify({"error": "Response not found"}), 404

    return jsonify(row_to_dict(row))


@app.route("/responses/<int:response_id>", methods=["PUT"])
def update_response(response_id):
    data = request.get_json()
    db = get_db()

    existing = db.execute(
        "SELECT * FROM Responses WHERE response_id = ?",
        (response_id,)
    ).fetchone()

    if existing is None:
        return jsonify({"error": "Response not found"}), 404

    updated_values = {
        "patient_id": data.get("patient_id", existing["patient_id"]),
        "response_date": data.get("response_date", existing["response_date"]),
        "adherence": data.get("adherence", existing["adherence"]),
        "non_compliance": data.get("non_compliance", existing["non_compliance"]),
        "difficulty_level": data.get("difficulty_level", existing["difficulty_level"]),
        "pain_level": data.get("pain_level", existing["pain_level"]),
        "progress_perception": data.get("progress_perception", existing["progress_perception"]),
        "issues": data.get("issues", existing["issues"]),
        "notes": data.get("notes", existing["notes"]),
    }

    patient = db.execute(
        "SELECT patient_id FROM Patients WHERE patient_id = ?",
        (updated_values["patient_id"],)
    ).fetchone()

    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    db.execute("""
        UPDATE Responses
        SET patient_id = ?, response_date = ?, adherence = ?, non_compliance = ?,
            difficulty_level = ?, pain_level = ?, progress_perception = ?,
            issues = ?, notes = ?
        WHERE response_id = ?
    """, (
        updated_values["patient_id"],
        updated_values["response_date"],
        updated_values["adherence"],
        updated_values["non_compliance"],
        updated_values["difficulty_level"],
        updated_values["pain_level"],
        updated_values["progress_perception"],
        updated_values["issues"],
        updated_values["notes"],
        response_id
    ))
    db.commit()

    return jsonify({"message": "Response updated"})


@app.route("/responses/<int:response_id>", methods=["DELETE"])
def delete_response(response_id):
    db = get_db()
    cur = db.execute("DELETE FROM Responses WHERE response_id = ?", (response_id,))
    db.commit()

    if cur.rowcount == 0:
        return jsonify({"error": "Response not found"}), 404

    return jsonify({"message": "Response deleted"})


# -------------------------
# Extra useful routes
# -------------------------

@app.route("/patients/<int:patient_id>/responses", methods=["GET"])
def get_patient_responses(patient_id):
    db = get_db()

    patient = db.execute(
        "SELECT * FROM Patients WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()

    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    rows = db.execute("""
        SELECT * FROM Responses
        WHERE patient_id = ?
        ORDER BY response_date DESC, response_id DESC
    """, (patient_id,)).fetchall()

    return jsonify([row_to_dict(row) for row in rows])


@app.route("/patients/<int:patient_id>/responses/weekly", methods=["GET"])
def get_patient_weekly_responses(patient_id):
    db = get_db()

    patient = db.execute(
        "SELECT * FROM Patients WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()

    if patient is None:
        return jsonify({"error": "Patient not found"}), 404

    rows = db.execute("""
        SELECT * FROM Responses
        WHERE patient_id = ?
          AND response_date >= datetime('now', '-7 days')
        ORDER BY response_date DESC, response_id DESC
    """, (patient_id,)).fetchall()

    return jsonify([row_to_dict(row) for row in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000, debug=False)