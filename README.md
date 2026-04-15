# Clinic API

Flask + SQLite API for managing **patients**, **consults**, and **responses**, designed to be called from internal tools and a Telegram bot. 

## Features

- Patients with optional Telegram chat linking.   
- Consults with **patient name auto-filled**, and flexible raw/AI/additional instructions.   
- Responses tracking adherence, pain, and subjective progress, queryable globally or per patient and by week.   
- Simple API key protection for write and sensitive routes. 

## Tech stack

- Python, Flask  
- SQLite (`sqlite3`)  
- `python-dotenv` for configuration 

---

## Environment & setup

### 1. Install dependencies

```bash
pip install flask python-dotenv requests
```

### 2. Environment variables

Create a `.env` in the same folder as `app.py`:

```env
DATABASE_PATH=clinic.db
INTERNAL_API_KEY=your-secret-key
PORT=5000
```

- `DATABASE_PATH`: path to the SQLite file.   
- `INTERNAL_API_KEY`: shared secret for internal services and the Telegram bot.   
- `PORT`: port for the Flask server. 

### 3. Run the API

```bash
python app.py
```

Server runs on `http://0.0.0.0:PORT` (default `5000`). 

---

## Authentication

Write and sensitive endpoints use a simple API key:

- Header: `X-API-KEY: <INTERNAL_API_KEY>` 

If `INTERNAL_API_KEY` is not set, the key check is disabled and endpoints behave as open. 

Example:

```bash
curl http://127.0.0.1:5000/patients \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{"patient_name": "John Tan"}'
```

---

## Database schema

Created in `init_db()` inside `app.py`. 

### Patients

```sql
CREATE TABLE IF NOT EXISTS Patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    telegram_chat_id TEXT
);
```

| Column             | Type    | Notes                          |
|--------------------|---------|--------------------------------|
| `patient_id`       | INTEGER | PK, autoincrement              |
| `patient_name`     | TEXT    | Required                       |
| `telegram_chat_id` | TEXT    | Nullable; used by Telegram bot |



### Consults

```sql
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
```

| Column                             | Type    | Notes                                                   |
|------------------------------------|---------|---------------------------------------------------------|
| `consult_id`                       | INTEGER | PK, autoincrement                                       |
| `patient_id`                       | INTEGER | FK → Patients.patient_id                                |
| `patient_name`                     | TEXT    | Snapshot of patient name, auto‑loaded from Patients     |
| `attending_name`                   | TEXT    | Required                                                |
| `consult_date`                     | TEXT    | Default: now (localtime)                                |
| `raw_attending_instructions`       | TEXT    | Optional                                                |
| `ai_attending_instructions`        | TEXT    | Optional (set by AI or later edits)                     |
| `additional_attending_instructions`| TEXT    | Optional (extra human notes/overrides)                  |



### Responses

```sql
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
);
```

| Column               | Type    | Notes                                  |
|----------------------|---------|----------------------------------------|
| `response_id`        | INTEGER | PK, autoincrement                      |
| `patient_id`         | INTEGER | FK → Patients.patient_id               |
| `consult_id`         | INTEGER | Nullable FK → Consults.consult_id      |
| `response_date`      | TEXT    | Default: now (localtime)               |
| `adherence`          | INTEGER | 1–5                                    |
| `non_compliance`     | TEXT    | Optional                               |
| `difficulty_level`   | INTEGER | 1–5                                    |
| `pain_level`         | INTEGER | 0–10                                   |
| `progress_perception`| TEXT    | Required                               |
| `issues`             | TEXT    | Optional                               |
| `notes`              | TEXT    | Optional                               |



> Note: If you previously had a different `Consults` schema (with `attending_id`, `raw_input`, `exercise`, etc.), you must create a **new database** or write a migration. `CREATE TABLE IF NOT EXISTS` will not change existing tables. 

---

## Seeding

Use `seed_db.py` to seed **10 patients**, **20 consults**, and **70 responses** matching this schema. [file:48]

```bash
python seed_db.py
```

The seeder:

- Inserts 10 patients (first 6 with Telegram IDs). [file:48]  
- Inserts 20 consults with random `attending_name` and optional instruction fields. [file:48]  
- Inserts 70 responses, tied to consults when possible with realistic dates. [file:48]

---

## Endpoints

Base URL: `http://<host>:<port>`

### Health

#### `GET /health`

Healthcheck.

Response:

```json
{ "status": "ok" }
```



---

## Patients

### `GET /patients`

List all patients (newest first).

```bash
curl http://127.0.0.1:5000/patients
```



---

### `GET /patients/<patient_id>`

Get a single patient.

```bash
curl http://127.0.0.1:5000/patients/1
```

Response 404:

```json
{ "error": "Patient not found" }
```



---

### `POST /patients`

Create a patient.

- Requires `X-API-KEY`. 

Body:

```json
{
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

Response:

```json
{
  "message": "Patient created",
  "patient_id": 1
}
```



---

### `PATCH /patients/<patient_id>/link-telegram` (also accepts POST)

Link or update a patient’s Telegram chat.

- Requires `X-API-KEY`.   
- Used by the Telegram bot `/start <patient_id>` flow.

Body:

```json
{
  "telegram_chat_id": "123456789"
}
```

Response:

```json
{
  "message": "Telegram chat updated",
  "patient_id": 1,
  "telegram_chat_id": "123456789"
}
```



---

### `GET /patients/by-telegram/<telegram_chat_id>`

Look up a patient by Telegram chat ID.

- Requires `X-API-KEY`. 

```bash
curl http://127.0.0.1:5000/patients/by-telegram/123456789 \
  -H "X-API-KEY: your-secret-key"
```

Response:

```json
{
  "patient_id": 1,
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```



---

## Consults

### `GET /consults`

List **all consults**.

- Requires `X-API-KEY`. 

```bash
curl http://127.0.0.1:5000/consults \
  -H "X-API-KEY: your-secret-key"
```

Returns all rows from `Consults` ordered by `consult_date DESC, consult_id DESC`. 

---

### `GET /consults/<consult_id>`

Get a single consult.

```bash
curl http://127.0.0.1:5000/consults/1
```

Response 404:

```json
{ "error": "Consult not found" }
```



---

### `GET /patients/<patient_id>/consults`

List all consults for a given patient.

```bash
curl http://127.0.0.1:5000/patients/1/consults \
  -H "X-API-KEY: your-secret-key"
```

Returns consults ordered by `consult_date DESC, consult_id DESC`. 

---

### `POST /consults`

Create a consult (new behaviour).

- Requires `X-API-KEY`.   
- Required: `patient_id`, `attending_name`.  
- Optional: `raw_attending_instructions`, `ai_attending_instructions`, `additional_attending_instructions`, `consult_date`.   
- `patient_name` is automatically loaded from `Patients` by `patient_id`. 

Body:

```json
{
  "patient_id": 1,
  "attending_name": "Dr Lim",
  "raw_attending_instructions": "Initial assessment, prescribe knee flexion exercises.",
  "ai_attending_instructions": null,
  "additional_attending_instructions": null
}
```

Response:

```json
{
  "message": "Consult created",
  "consult_id": 1
}
```



---

### `PATCH /consults/<consult_id>/instructions`

Update any combination of the three instruction fields.

- Requires `X-API-KEY`.   
- You can send one, two, or all three fields; unspecified ones are left unchanged.  
- Passing `null` will clear a field. 

Body (all three):

```json
{
  "raw_attending_instructions": "Updated raw instructions",
  "ai_attending_instructions": "Updated AI summary",
  "additional_attending_instructions": "Updated extra notes"
}
```

Body (one field):

```json
{
  "ai_attending_instructions": "AI-only update"
}
```

Example:

```bash
curl -X PATCH http://127.0.0.1:5000/consults/1/instructions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{"ai_attending_instructions": "AI-only update"}'
```

Response:

```json
{
  "message": "Consult instructions updated",
  "consult": {
    "...": "full consult row"
  }
}
```

If no instruction fields are provided:

```json
{
  "error": "At least one of raw_attending_instructions, ai_attending_instructions, additional_attending_instructions must be provided"
}
```



---

## Responses

### `POST /responses`

Create a response.

- Requires `X-API-KEY`.   
- Validates `patient_id` exists; if `consult_id` provided, validates consult exists. 

Required:

- `patient_id`
- `adherence` (1–5)
- `difficulty_level` (1–5)
- `pain_level` (0–10)
- `progress_perception`

Optional:

- `consult_id`
- `response_date`
- `non_compliance`
- `issues`
- `notes`

Example:

```bash
curl -X POST http://127.0.0.1:5000/responses \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{
    "patient_id": 1,
    "consult_id": 1,
    "adherence": 4,
    "difficulty_level": 2,
    "pain_level": 1,
    "progress_perception": "Better",
    "non_compliance": "Missed one session",
    "issues": "Mild stiffness",
    "notes": "Feels improved overall"
  }'
```

Response:

```json
{
  "message": "Response created",
  "response_id": 1
}
```



---

### `GET /responses`

List all responses.

- Requires `X-API-KEY`. 

```bash
curl http://127.0.0.1:5000/responses \
  -H "X-API-KEY: your-secret-key"
```

Returns all rows ordered by `response_date DESC, response_id DESC`. 

---

### `GET /patients/<patient_id>/responses`

List all responses for a specific patient.

- Requires `X-API-KEY`. 

```bash
curl http://127.0.0.1:5000/patients/1/responses \
  -H "X-API-KEY: your-secret-key"
```



---

### `GET /patients/<patient_id>/responses/weekly`

List responses from the last 7 days for a patient.

- Requires `X-API-KEY`. 

```bash
curl http://127.0.0.1:5000/patients/1/responses/weekly \
  -H "X-API-KEY: your-secret-key"
```



---

### `GET /patients/<patient_id>/responses/by-week?end_date=YYYY-MM-DD`

List responses in a 7‑day window ending on `end_date` (inclusive).

- Requires `X-API-KEY`.   
- `end_date` must be `YYYY-MM-DD`. 

Example:

```bash
curl "http://127.0.0.1:5000/patients/1/responses/by-week?end_date=2026-04-15" \
  -H "X-API-KEY: your-secret-key"
```

Response:

```json
{
  "patient_id": 1,
  "start_date": "2026-04-09",
  "end_date": "2026-04-15",
  "responses": [
    { "...": "response rows" }
  ]
}
```



---

## Error responses

- Wrong or missing API key (when configured):

```json
{ "error": "Unauthorized" }
```



- Missing required fields:

```json
{
  "error": "Missing required fields",
  "missing": ["adherence", "..."]
}
```



- Resource not found:

```json
{ "error": "Patient not found" }
```

or

```json
{ "error": "Consult not found" }
```

