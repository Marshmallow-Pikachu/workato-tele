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

# Workato Integration README

This document describes the local Flask API endpoints for the patient-consult-response system so teammates can integrate it with Workato. The API uses JSON request and response bodies, and protected endpoints require an internal API key sent in the `X-API-KEY` header. [cite:375][cite:369]

## Base URL

Use the base URL of the Windows machine hosting the Flask app:

```txt
http://<WINDOWS_MACHINE_IP>:5000
```

A simple connectivity check is available at `/health`, which can be used in Workato to verify the service is reachable before attempting authenticated actions. [cite:370][cite:374]

## Authentication

Protected endpoints require this header:

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
```

For `POST` requests, also send:

```http
Content-Type: application/json
Accept: application/json
```

Workato supports custom headers and JSON request bodies in REST-style integrations and custom connector setups, so this authentication style is compatible with a typical Workato recipe. [cite:375][cite:369]

## Endpoint summary

| Method | Path | Auth required | Purpose |
|---|---|---:|---|
| GET | `/health` | No | Service health check |
| GET | `/patients` | No | List all patients |
| GET | `/patients/<patient_id>` | No | Get one patient |
| POST | `/patients` | Yes | Create a patient |
| POST | `/patients/<patient_id>/link-telegram` | Yes | Link Telegram chat ID |
| GET | `/patients/by-telegram/<telegram_chat_id>` | Yes | Find patient by Telegram chat ID |
| POST | `/consults` | Yes | Create a consult |
| GET | `/consults/<consult_id>` | No | Get one consult |
| GET | `/patients/<patient_id>/consults` | No | List a patient’s consults |
| POST | `/responses` | Yes | Create a patient response |
| GET | `/patients/<patient_id>/responses/weekly` | Yes | Get last 7 days of responses |

The API follows standard REST-like route patterns, which makes it straightforward to map into Workato actions for create, lookup, and reporting steps. [cite:369][cite:374]

## Endpoints in detail

### GET /health

Use this endpoint to test that the API is reachable from Workato or another client.

**Response**

```json
{
  "status": "ok"
}
```

This is a lightweight health endpoint and is useful as a first-step connectivity or monitoring check. [cite:370][cite:374]

### GET /patients

Returns all patients.

**Response**

```json
[
  {
    "patient_id": 1,
    "patient_name": "John Tan",
    "telegram_chat_id": "123456789"
  }
]
```

### GET /patients/<patient_id>

Returns a single patient by ID.

**Example**

```txt
GET /patients/1
```

**Response**

```json
{
  "patient_id": 1,
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

### POST /patients

Creates a new patient record.

**Headers**

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
Content-Type: application/json
Accept: application/json
```

**Request body**

```json
{
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

`patient_name` is required, while `telegram_chat_id` is optional. The endpoint returns a JSON body with the newly created `patient_id`, which is the common REST pattern for successful resource creation. [cite:359][cite:368]

**Success response**

```json
{
  "message": "Patient created",
  "patient_id": 1
}
```

### POST /patients/<patient_id>/link-telegram

Stores a Telegram chat ID against an existing patient.

**Example**

```txt
POST /patients/1/link-telegram
```

**Headers**

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
Content-Type: application/json
Accept: application/json
```

**Request body**

```json
{
  "telegram_chat_id": "123456789"
}
```

**Success response**

```json
{
  "message": "Linked",
  "patient_id": 1,
  "telegram_chat_id": "123456789"
}
```

### GET /patients/by-telegram/<telegram_chat_id>

Finds a patient by Telegram chat ID.

**Example**

```txt
GET /patients/by-telegram/123456789
```

**Headers**

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
Accept: application/json
```

**Response**

```json
{
  "patient_id": 1,
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

### POST /consults

Creates a consult linked to a patient.

**Headers**

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
Content-Type: application/json
Accept: application/json
```

**Request body**

```json
{
  "attending_id": 101,
  "patient_id": 1,
  "consult_date": "2026-04-12 15:30:00",
  "raw_input": "Lower back discomfort after sitting",
  "exercise": "Bird Dog",
  "sets": 3,
  "reps": 10,
  "frequency": "Daily",
  "instructions": "Keep spine neutral and move slowly",
  "tips": "Stop if sharp pain occurs"
}
```

`consult_date` may be omitted if the server should use the current local datetime, which is a common SQLite pattern using a default datetime expression. [cite:312]

**Success response**

```json
{
  "message": "Consult created",
  "consult_id": 1
}
```

### GET /consults/<consult_id>

Returns a consult by ID.

**Example**

```txt
GET /consults/1
```

**Response**

```json
{
  "consult_id": 1,
  "attending_id": 101,
  "patient_id": 1,
  "consult_date": "2026-04-12 15:30:00",
  "raw_input": "Lower back discomfort after sitting",
  "exercise": "Bird Dog",
  "sets": 3,
  "reps": 10,
  "frequency": "Daily",
  "instructions": "Keep spine neutral and move slowly",
  "tips": "Stop if sharp pain occurs"
}
```

### GET /patients/<patient_id>/consults

Lists all consults for a patient.

**Example**

```txt
GET /patients/1/consults
```

**Response**

```json
[
  {
    "consult_id": 1,
    "attending_id": 101,
    "patient_id": 1,
    "consult_date": "2026-04-12 15:30:00",
    "raw_input": "Lower back discomfort after sitting",
    "exercise": "Bird Dog",
    "sets": 3,
    "reps": 10,
    "frequency": "Daily",
    "instructions": "Keep spine neutral and move slowly",
    "tips": "Stop if sharp pain occurs"
  }
]
```

### POST /responses

Creates a patient response or check-in.

**Headers**

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
Content-Type: application/json
Accept: application/json
```

**Request body**

```json
{
  "patient_id": 1,
  "consult_id": 1,
  "response_date": "2026-04-12 16:00:00",
  "adherence": 4,
  "non_compliance": "",
  "difficulty_level": 2,
  "pain_level": 1,
  "progress_perception": "Better",
  "issues": "",
  "notes": "Felt okay today"
}
```

Required fields are `patient_id`, `adherence`, `difficulty_level`, `pain_level`, and `progress_perception`, while the other fields can be omitted or provided as empty strings depending on recipe design. [cite:374]

**Success response**

```json
{
  "message": "Response created",
  "response_id": 1
}
```

### GET /patients/<patient_id>/responses/weekly

Returns all responses for the patient from the last 7 days.

**Example**

```txt
GET /patients/1/responses/weekly
```

**Headers**

```http
X-API-KEY: <YOUR_INTERNAL_API_KEY>
Accept: application/json
```

**Response**

```json
[
  {
    "response_id": 1,
    "patient_id": 1,
    "consult_id": 1,
    "response_date": "2026-04-12 16:00:00",
    "adherence": 4,
    "non_compliance": "",
    "difficulty_level": 2,
    "pain_level": 1,
    "progress_perception": "Better",
    "issues": "",
    "notes": "Felt okay today"
  }
]
```

This route is suitable for reporting or follow-up workflows because it already applies a last-7-days date filter in the API layer. SQLite date filters commonly use `datetime('now', '-7 days')` for this pattern. [cite:312]

## Common error responses

| Status | Meaning | Typical cause |
|---|---|---|
| `400` | Bad Request | Missing required JSON fields |
| `401` | Unauthorized | Missing or wrong `X-API-KEY` |
| `404` | Not Found | Patient or consult does not exist |
| `415` | Unsupported Media Type | Missing `Content-Type: application/json` on POST |

Workato recipes should branch on these status codes so that invalid inputs, auth issues, and formatting issues can be handled explicitly rather than failing silently. Workato’s API tooling is designed around predictable HTTP status handling and structured request/response bodies. [cite:375][cite:370]

## Suggested Workato flow

A typical Workato automation sequence for this API is:

1. Call `POST /patients` to create the patient.
2. Call `POST /consults` to store the consult details.
3. Optionally call `POST /patients/<patient_id>/link-telegram` after the bot is linked.
4. Call `POST /responses` when a patient check-in arrives.
5. Call `GET /patients/<patient_id>/responses/weekly` for dashboards or reminders.

This mirrors a standard REST integration flow where create, lookup, and reporting endpoints are composed into recipe steps. [cite:369][cite:375]
