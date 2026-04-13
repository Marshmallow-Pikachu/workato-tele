# Clinic API

Flask + SQLite API for managing **patients**, **consults**, and **responses**, designed to be called from internal tools and a Telegram bot.

## Features

- Patients with optional Telegram chat linking.  
- Consults with attending information and separate raw / AI / additional instructions.  
- Responses with adherence, pain, and subjective progress, queryable by patient and time window.  
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

Write and sensitive endpoints require an internal key:

- Header: `X-API-KEY: <INTERNAL_API_KEY>`

If `INTERNAL_API_KEY` is omitted in the environment, the API key check is effectively disabled and endpoints behave as open.

Example:

```bash
curl http://127.0.0.1:5000/patients \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{"patient_name": "John Tan"}'
```

---

## Database schema

### Patients

| Column             | Type    | Notes                          |
|--------------------|---------|--------------------------------|
| `patient_id`       | INTEGER | PK, autoincrement              |
| `patient_name`     | TEXT    | Required                       |
| `telegram_chat_id` | TEXT    | Nullable; used by Telegram bot |

### Consults

| Column                             | Type    | Notes                                           |
|------------------------------------|---------|-------------------------------------------------|
| `consult_id`                       | INTEGER | PK, autoincrement                               |
| `patient_id`                       | INTEGER | FK → Patients.patient_id                        |
| `patient_name`                     | TEXT    | Snapshot of patient name at consult time        |
| `attending_id`                     | INTEGER | Required                                        |
| `attending_name`                   | TEXT    | Required                                        |
| `consult_date`                     | TEXT    | Default: now (localtime)                        |
| `raw_attending_instructions`       | TEXT    | Required, original instructions                 |
| `ai_attending_instructions`        | TEXT    | Nullable, set later by AI                       |
| `additional_attending_instructions`| TEXT    | Nullable, extra human edits                     |

### Responses

| Column               | Type    | Notes                                  |
|----------------------|---------|----------------------------------------|
| `response_id`        | INTEGER | PK, autoincrement                     |
| `patient_id`         | INTEGER | FK → Patients.patient_id              |
| `consult_id`         | INTEGER | Nullable FK → Consults.consult_id     |
| `response_date`      | TEXT    | Default: now (localtime)              |
| `adherence`          | INTEGER | 1–5                                   |
| `non_compliance`     | TEXT    | Optional                               |
| `difficulty_level`   | INTEGER | 1–5                                   |
| `pain_level`         | INTEGER | 0–10                                  |
| `progress_perception`| TEXT    | Required                               |
| `issues`             | TEXT    | Optional                               |
| `notes`              | TEXT    | Optional                               |

> Note: If you are migrating from a previous schema (with `raw_input`, `exercise`, `sets`, `reps`, `frequency`, `instructions`), you must create a **new database** or write a migration script; `CREATE TABLE IF NOT EXISTS` will not alter existing tables.

---

## Endpoints

Base URL: `http://<host>:<port>`

### Health

#### `GET /health`

Simple healthcheck.

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

Get one patient by ID.

```bash
curl http://127.0.0.1:5000/patients/1
```

---

### `POST /patients`

Create a patient.

- Requires `X-API-KEY`.
- Body: JSON.

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

### `POST /consults`

Create a consult.

- Requires `X-API-KEY`.
- Validates that `patient_id` exists.

Required fields:

- `patient_id`
- `attending_id`
- `attending_name`
- `raw_attending_instructions`

Optional:

- `patient_name` (defaults to current patient name)
- `consult_date`
- `ai_attending_instructions`
- `additional_attending_instructions`

Example:

```bash
curl -X POST http://127.0.0.1:5000/consults \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{
    "patient_id": 1,
    "attending_id": 10,
    "attending_name": "Dr Lee",
    "raw_attending_instructions": "Perform mobility exercises twice daily",
    "ai_attending_instructions": null,
    "additional_attending_instructions": null
  }'
```

Response:

```json
{
  "message": "Consult created",
  "consult_id": 1
}
```

---

### `GET /consults/<consult_id>`

Get a single consult.

```bash
curl http://127.0.0.1:5000/consults/1
```

---

### `GET /patients/<patient_id>/consults`

Get all consults for a patient, latest first.

```bash
curl http://127.0.0.1:5000/patients/1/consults
```

---

### `PATCH /consults/<consult_id>/ai-attending-instructions`

Update `ai_attending_instructions`.

- Requires `X-API-KEY`.

Body:

```json
{
  "ai_attending_instructions": "Summarised rehab plan generated by AI"
}
```

Example:

```bash
curl -X PATCH http://127.0.0.1:5000/consults/1/ai-attending-instructions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{"ai_attending_instructions": "Summarised rehab plan generated by AI"}'
```

---

### `PATCH /consults/<consult_id>/additional-attending-instructions`

Update `additional_attending_instructions`.

- Requires `X-API-KEY`.

Body:

```json
{
  "additional_attending_instructions": "Avoid stairs for 3 days"
}
```

Example:

```bash
curl -X PATCH http://127.0.0.1:5000/consults/1/additional-attending-instructions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{"additional_attending_instructions": "Avoid stairs for 3 days"}'
```

---

## Responses

### `POST /responses`

Create a response (e.g., from the Telegram bot).

- Requires `X-API-KEY`.
- Validates patient exists; if `consult_id` provided, validates consult exists.

Required fields:

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

List all responses (latest first).

- Requires `X-API-KEY`.

```bash
curl http://127.0.0.1:5000/responses \
  -H "X-API-KEY: your-secret-key"
```

---

### `GET /patients/<patient_id>/responses`

List all responses for a given patient.

- Requires `X-API-KEY`.

```bash
curl http://127.0.0.1:5000/patients/1/responses \
  -H "X-API-KEY: your-secret-key"
```

---

### `GET /patients/<patient_id>/responses/weekly`

List responses for the last 7 days.

- Requires `X-API-KEY`.

```bash
curl http://127.0.0.1:5000/patients/1/responses/weekly \
  -H "X-API-KEY: your-secret-key"
```

---

### `GET /patients/<patient_id>/responses/by-week?end_date=YYYY-MM-DD`

List responses in a 7‑day window ending on `end_date` (inclusive).

- Requires `X-API-KEY`.
- `end_date` format: `YYYY-MM-DD`.

Example:

```bash
curl "http://127.0.0.1:5000/patients/1/responses/by-week?end_date=2026-04-13" \
  -H "X-API-KEY: your-secret-key"
```

Response:

```json
{
  "patient_id": 1,
  "start_date": "2026-04-07",
  "end_date": "2026-04-13",
  "responses": [
    {
      "response_id": 1,
      "patient_id": 1,
      "consult_id": 1,
      "response_date": "2026-04-13 09:00:00",
      "adherence": 4,
      "non_compliance": "Missed one session",
      "difficulty_level": 2,
      "pain_level": 1,
      "progress_perception": "Better",
      "issues": "Mild stiffness",
      "notes": "Feels improved overall"
    }
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
