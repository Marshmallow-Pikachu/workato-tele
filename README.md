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
