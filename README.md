# Clinic API README

This README documents the cleaned-up Flask API and the updated database structure based on the attached `app.py`, which currently uses Flask, `sqlite3`, API-key-protected write routes, and Telegram bot integration points.[file:43][file:44]

## Overview

The API manages three core resources: `Patients`, `Consults`, and `Responses`.[file:43] The updated version preserves the existing response payload structure while changing the consult schema to store attending instructions and adding update methods for AI-generated and additional attending instructions.[file:43]

## Updated database structure

### Patients

| Column | Type | Notes |
|---|---|---|
| `patient_id` | INTEGER | Primary key, auto-increment.[file:43] |
| `patient_name` | TEXT | Required.[file:43] |
| `telegram_chat_id` | TEXT | Nullable; used by the Telegram bot to identify a patient chat link.[file:43][file:44] |

### Consults

| Column | Type | Notes |
|---|---|---|
| `consult_id` | INTEGER | Primary key, auto-increment. |
| `patient_id` | INTEGER | Foreign key to `Patients.patient_id`. |
| `patient_name` | TEXT | Stored with the consult for convenience and history snapshots. |
| `attending_id` | INTEGER | Required attending identifier. |
| `attending_name` | TEXT | Required attending name. |
| `consult_date` | TEXT | Defaults to current local datetime. |
| `raw_attending_instructions` | TEXT | Required original attending instructions. |
| `ai_attending_instructions` | TEXT | Nullable; can be updated later. |
| `additional_attending_instructions` | TEXT | Nullable; can be updated later. |

### Responses

| Column | Type | Notes |
|---|---|---|
| `response_id` | INTEGER | Primary key, auto-increment.[file:43] |
| `patient_id` | INTEGER | Foreign key; the main lookup field for response queries.[file:43] |
| `consult_id` | INTEGER | Optional foreign key to `Consults.consult_id`.[file:43] |
| `response_date` | TEXT | Defaults to current local datetime.[file:43] |
| `adherence` | INTEGER | Required, must be between 1 and 5.[file:43] |
| `non_compliance` | TEXT | Optional.[file:43] |
| `difficulty_level` | INTEGER | Required, must be between 1 and 5.[file:43] |
| `pain_level` | INTEGER | Required, must be between 0 and 10.[file:43] |
| `progress_perception` | TEXT | Required.[file:43] |
| `issues` | TEXT | Optional.[file:43] |
| `notes` | TEXT | Optional.[file:43] |

## Important migration note

The original attached `app.py` creates a different `Consults` schema with fields such as `raw_input`, `exercise`, `sets`, `reps`, `frequency`, and `instructions`.[file:43] Because `CREATE TABLE IF NOT EXISTS` does not alter existing tables, an existing database file will not automatically match the new schema, so either a fresh database file or an explicit migration is required.[file:43]

## Setup

### 1. Install dependencies

```bash
pip install flask python-dotenv
```

### 2. Create environment variables

Create a `.env` file:

```env
DATABASE_PATH=clinic.db
INTERNAL_API_KEY=your-secret-key
PORT=5000
```

### 3. Run the API

```bash
python app.py
```

### 4. Health check

```bash
curl http://127.0.0.1:5000/health
```

## Authentication

Read routes are mostly open in the current implementation, but write and sensitive lookup endpoints use the `X-API-KEY` header through the `require_api_key()` helper in the attached app design.[file:43] The Telegram bot also sends this same header when calling the API, so the API and bot should share the same internal key value.[file:44]

Example:

```bash
-H "X-API-KEY: your-secret-key"
```

## API endpoints

## Patients

### `GET /patients`

Returns all patients ordered by newest first.

```bash
curl http://127.0.0.1:5000/patients
```

### `GET /patients/<patient_id>`

Returns one patient by ID.

```bash
curl http://127.0.0.1:5000/patients/1
```

### `POST /patients`

Creates a patient.

Request body:

```json
{
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

Example:

```bash
curl -X POST http://127.0.0.1:5000/patients \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{
    "patient_name": "John Tan",
    "telegram_chat_id": "123456789"
  }'
```

### `PATCH /patients/<patient_id>/link-telegram`

Links or updates a patient's Telegram chat ID. This keeps compatibility with the Telegram bot flow in `bot_main.py`, which links a patient on `/start <patient_id>` and later looks up the patient by Telegram chat ID before sending response data.[file:44]

Request body:

```json
{
  "telegram_chat_id": "123456789"
}
```

Example:

```bash
curl -X PATCH http://127.0.0.1:5000/patients/1/link-telegram \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-secret-key" \
  -d '{"telegram_chat_id": "123456789"}'
```

### `GET /patients/by-telegram/<telegram_chat_id>`

Looks up a patient by Telegram chat ID.

```bash
curl http://127.0.0.1:5000/patients/by-telegram/123456789 \
  -H "X-API-KEY: your-secret-key"
```

## Consults

### `POST /consults`

Creates a consult record.

Required fields:
- `patient_id`
- `attending_id`
- `attending_name`
- `raw_attending_instructions`

Optional fields:
- `patient_name`
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

### `GET /consults/<consult_id>`

Returns a single consult.

```bash
curl http://127.0.0.1:5000/consults/1
```

### `GET /patients/<patient_id>/consults`

Returns all consults for a patient.

```bash
curl http://127.0.0.1:5000/patients/1/consults
```

### `PATCH /consults/<consult_id>/ai-attending-instructions`

Updates `ai_attending_instructions`.

Request body:

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

### `PATCH /consults/<consult_id>/additional-attending-instructions`

Updates `additional_attending_instructions`.

Request body:

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

## Responses

### `POST /responses`

Creates a response record. This stays compatible with the Telegram bot, which currently sends `patient_id`, `adherence`, `difficulty_level`, `pain_level`, `progress_perception`, `non_compliance`, `issues`, and `notes`.[file:44]

Required fields:
- `patient_id`
- `adherence`
- `difficulty_level`
- `pain_level`
- `progress_perception`

Optional fields:
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
    "notes": "Feels improved"
  }'
```

### `GET /responses`

Returns all responses.

```bash
curl http://127.0.0.1:5000/responses \
  -H "X-API-KEY: your-secret-key"
```

### `GET /patients/<patient_id>/responses`

Returns all responses for a patient.

```bash
curl http://127.0.0.1:5000/patients/1/responses \
  -H "X-API-KEY: your-secret-key"
```

### `GET /patients/<patient_id>/responses/weekly`

Returns responses from the last 7 days.

```bash
curl http://127.0.0.1:5000/patients/1/responses/weekly \
  -H "X-API-KEY: your-secret-key"
```

### `GET /patients/<patient_id>/responses/by-week?end_date=YYYY-MM-DD`

Returns responses for a 7-day window ending on the provided date. The window is inclusive, so the API uses `end_date` and the six prior days.[file:43]

```bash
curl "http://127.0.0.1:5000/patients/1/responses/by-week?end_date=2026-04-13" \
  -H "X-API-KEY: your-secret-key"
```

## Bot compatibility notes

The attached `bot_main.py` currently depends on three API paths: `/patients/<patient_id>/link-telegram`, `/patients/by-telegram/<chat_id>`, and `POST /responses`.[file:44] The cleaned API preserves those routes so the bot logic can continue working without major changes.[file:44]

The bot also sends `telegram_username` when linking a patient, but the attached API does not store that field, so it is ignored unless a future schema change adds it to `Patients`.[file:43][file:44]

## Suggested next steps

- Add explicit schema migration logic if you need to preserve an old `clinic.db` file with the previous `Consults` table shape.[file:43]
- Consider moving read routes behind the API key as well if this API will be exposed outside a trusted local environment.[file:43]
- If you later switch from SQLite to Supabase Postgres, the route design can stay similar while the database layer is replaced with a PostgreSQL driver or ORM.[file:43]
