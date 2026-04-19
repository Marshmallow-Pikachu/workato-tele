# Clinic Telegram API README

A Flask API for managing patients, consults, exercise responses, and Telegram-based reminder or instruction workflows. The API supports patient management, consult records, weekly response submission, and internal endpoints that trigger Telegram sends for reminders and exercise instructions. [file:2][file:3]

## Base URL

```text
http://<host>:<port>
```

Example:

```text
http://127.0.0.1:5000
```

## Authentication

Public endpoints do not require authentication, while protected endpoints require the `X-API-KEY` request header. In the Flask app, protected routes compare `X-API-KEY` against `INTERNAL_API_KEY` or `API_KEY` from the environment. [file:2]

### Protected request headers

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

For `GET` requests without a JSON body, `Content-Type` is optional, but `X-API-KEY` is still required on protected endpoints. [file:2]

## Common error response patterns

Most unsuccessful responses in the API follow these JSON structures. The exact message varies by endpoint, but the shape is consistent across the route handlers. [file:2]

### Unauthorized

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

### Validation error

Status: `400`

```json
{
  "error": "patient_name is required"
}
```

or

```json
{
  "error": "Missing required fields",
  "missing": ["patient_id", "adherence"]
}
```

### Not found

Status: `404`

```json
{
  "error": "Patient not found"
}
```

or

```json
{
  "error": "Consult not found"
}
```

### Unsupported media type

Status: `415`

```json
{
  "error": "Content-Type must be application/json"
}
```

### Internal send failure

Status: `500`

```json
{
  "error": "Failed to send instructions",
  "detail": "..."
}
```

## Endpoints

## Health

### `GET /health`

Checks whether the API is running. This endpoint is public and returns a simple health status object. [file:2]

#### Request header

None required.

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
{
  "status": "ok"
}
```

#### Unsuccessful JSON response structure

No custom unsuccessful response is defined for this route in the current handler. [file:2]

## Patients

### `GET /patients`

Returns all patients ordered by `patient_id` descending. This endpoint is public in the cleaned route design. [file:2]

#### Request header

None required.

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "patient_id": 3,
    "patient_name": "John Tan",
    "telegram_chat_id": "123456789"
  },
  {
    "patient_id": 2,
    "patient_name": "Mary Lim",
    "telegram_chat_id": null
  }
]
```

#### Unsuccessful JSON response structure

No custom unsuccessful response is defined for this route in the current handler. [file:2]

### `GET /patients/<patient_id>`

Returns one patient by ID and responds with `404` if the patient does not exist. [file:2]

#### Request header

None required.

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
{
  "patient_id": 3,
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

#### Unsuccessful JSON response structure

Status: `404`

```json
{
  "error": "Patient not found"
}
```

### `POST /patients`

Creates a new patient. This endpoint is protected and requires JSON input with `patient_name`, while `telegram_chat_id` is optional. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

#### Successful JSON response structure

Status: `201`

```json
{
  "message": "Patient created",
  "patient_id": 3
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `415`

```json
{
  "error": "Content-Type must be application/json"
}
```

Status: `400`

```json
{
  "error": "patient_name is required"
}
```

### `POST /patients/<patient_id>/link-telegram`
### `PATCH /patients/<patient_id>/link-telegram`

Links or updates a patient’s Telegram chat ID. The Telegram bot uses this endpoint during `/start <patient_id>` linking. The Flask handler updates `telegram_chat_id` and returns `404` if the patient does not exist. [file:1][file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "telegram_chat_id": "123456789",
  "telegram_username": "john_example"
}
```

The bot sends both fields, but the API currently only persists `telegram_chat_id`. [file:1][file:2]

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Telegram chat updated",
  "patient_id": 3,
  "telegram_chat_id": "123456789"
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `415`

```json
{
  "error": "Content-Type must be application/json"
}
```

Status: `404`

```json
{
  "error": "Patient not found"
}
```

### `GET /patients/by-telegram/<telegram_chat_id>`

Looks up a patient by Telegram chat ID. The Telegram bot uses this endpoint before starting the weekly response flow. This endpoint is protected. [file:1][file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
{
  "patient_id": 3,
  "patient_name": "John Tan",
  "telegram_chat_id": "123456789"
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `404`

```json
{
  "error": "Patient not found"
}
```

## Consults

### `GET /consults`

Returns all consults ordered by `consult_date` descending and then `consult_id` descending. This endpoint is protected. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "consult_id": 5,
    "patient_id": 3,
    "patient_name": "John Tan",
    "attending_name": "Dr Lee",
    "consult_date": "2026-04-19 10:30:00",
    "raw_attending_instructions": "Original notes",
    "ai_attending_instructions": "Summarized exercise plan",
    "additional_attending_instructions": "Extra notes"
  }
]
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

### `POST /consults`

Creates a consult linked to an existing patient. This endpoint requires `patient_id` and `attending_name`, while `consult_date` and the instruction fields are optional. The API loads the patient name from the `Patients` table before inserting the consult. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "patient_id": 3,
  "attending_name": "Dr Lee",
  "consult_date": "2026-04-19 10:30:00",
  "raw_attending_instructions": "Original notes from therapist",
  "ai_attending_instructions": "Summarized exercise plan",
  "additional_attending_instructions": "Avoid overexertion"
}
```

#### Successful JSON response structure

Status: `201`

```json
{
  "message": "Consult created",
  "consult_id": 5
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `415`

```json
{
  "error": "Content-Type must be application/json"
}
```

Status: `400`

```json
{
  "error": "patient_id is required"
}
```

or

```json
{
  "error": "attending_name is required"
}
```

Status: `404`

```json
{
  "error": "Patient not found"
}
```

### `GET /consults/<consult_id>`

Returns one consult by ID. In the cleaned rewritten routes, this endpoint is treated as protected for consistency. It returns `404` when the consult is missing. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
{
  "consult_id": 5,
  "patient_id": 3,
  "patient_name": "John Tan",
  "attending_name": "Dr Lee",
  "consult_date": "2026-04-19 10:30:00",
  "raw_attending_instructions": "Original notes",
  "ai_attending_instructions": "Summarized exercise plan",
  "additional_attending_instructions": "Extra notes"
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `404`

```json
{
  "error": "Consult not found"
}
```

### `GET /patients/<patient_id>/consults`

Returns all consults for a specific patient, ordered newest first. The reminder sender uses this endpoint to determine which consult to use when falling back to the latest consult. [file:2][file:3]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "consult_id": 5,
    "patient_id": 3,
    "patient_name": "John Tan",
    "attending_name": "Dr Lee",
    "consult_date": "2026-04-19 10:30:00",
    "raw_attending_instructions": "Original notes",
    "ai_attending_instructions": "Summarized exercise plan",
    "additional_attending_instructions": "Extra notes"
  }
]
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

### `PATCH /consults/<consult_id>/instructions`

Partially updates one or more instruction fields on a consult. At least one of `raw_attending_instructions`, `ai_attending_instructions`, or `additional_attending_instructions` must be present in the request body. The handler allows explicit `null` values to clear fields. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "ai_attending_instructions": "Updated summarized instructions",
  "additional_attending_instructions": "Updated additional notes"
}
```

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Consult instructions updated",
  "consult": {
    "consult_id": 5,
    "patient_id": 3,
    "patient_name": "John Tan",
    "attending_name": "Dr Lee",
    "consult_date": "2026-04-19 10:30:00",
    "raw_attending_instructions": "Original notes",
    "ai_attending_instructions": "Updated summarized instructions",
    "additional_attending_instructions": "Updated additional notes"
  }
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `415`

```json
{
  "error": "Content-Type must be application/json"
}
```

Status: `400`

```json
{
  "error": "At least one instruction field must be provided"
}
```

Status: `404`

```json
{
  "error": "Consult not found"
}
```

## Responses

### `POST /responses`

Creates a weekly exercise response. The Telegram bot submits to this endpoint after a patient completes the questionnaire flow. The required fields are `patient_id`, `adherence`, `difficulty_level`, `pain_level`, and `progress_perception`, while `consult_id`, `non_compliance`, `issues`, `notes`, and `response_date` are optional. [file:1][file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "patient_id": 3,
  "consult_id": 5,
  "response_date": "2026-04-19 20:00:00",
  "adherence": 5,
  "non_compliance": null,
  "difficulty_level": 3,
  "pain_level": 2,
  "progress_perception": "Better",
  "issues": "none",
  "notes": "Feeling better this week"
}
```

#### Successful JSON response structure

Status: `201`

```json
{
  "message": "Response created",
  "response_id": 10
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `415`

```json
{
  "error": "Content-Type must be application/json"
}
```

Status: `400`

```json
{
  "error": "Missing required fields",
  "missing": ["patient_id", "adherence", "difficulty_level", "pain_level", "progress_perception"]
}
```

Status: `404`

```json
{
  "error": "Patient not found"
}
```

or

```json
{
  "error": "Consult not found"
}
```

### `GET /responses`

Returns all responses ordered by `response_date` descending and then `response_id` descending. This endpoint is protected. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "response_id": 10,
    "patient_id": 3,
    "consult_id": 5,
    "response_date": "2026-04-19 20:00:00",
    "adherence": 5,
    "non_compliance": null,
    "difficulty_level": 3,
    "pain_level": 2,
    "progress_perception": "Better",
    "issues": "none",
    "notes": "Feeling better this week"
  }
]
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

### `GET /patients/<patient_id>/responses`

Returns all responses for a specific patient. The handler checks that the patient exists before returning the list. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "response_id": 10,
    "patient_id": 3,
    "consult_id": 5,
    "response_date": "2026-04-19 20:00:00",
    "adherence": 5,
    "non_compliance": null,
    "difficulty_level": 3,
    "pain_level": 2,
    "progress_perception": "Better",
    "issues": "none",
    "notes": "Feeling better this week"
  }
]
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `404`

```json
{
  "error": "Patient not found"
}
```

### `GET /consults/<consult_id>/responses`

Returns all responses associated with a specific consult. This consult-centric lookup is part of the cleaned rewritten route design so responses can be viewed per consult rather than only per patient. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "response_id": 10,
    "patient_id": 3,
    "consult_id": 5,
    "response_date": "2026-04-19 20:00:00",
    "adherence": 5,
    "non_compliance": null,
    "difficulty_level": 3,
    "pain_level": 2,
    "progress_perception": "Better",
    "issues": "none",
    "notes": "Feeling better this week"
  }
]
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

### `GET /patients/<patient_id>/responses/weekly`

Returns responses for the last 7 days for a given patient. This endpoint is protected. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
[
  {
    "response_id": 10,
    "patient_id": 3,
    "consult_id": 5,
    "response_date": "2026-04-19 20:00:00",
    "adherence": 5,
    "non_compliance": null,
    "difficulty_level": 3,
    "pain_level": 2,
    "progress_perception": "Better",
    "issues": "none",
    "notes": "Feeling better this week"
  }
]
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

### `GET /patients/<patient_id>/responses/by-week?end_date=YYYY-MM-DD`

Returns responses for the 7-day window ending on `end_date`. The query parameter is required and must match `YYYY-MM-DD`. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
```

#### Request body

None.

#### Successful JSON response structure

Status: `200`

```json
{
  "patient_id": 3,
  "start_date": "2026-04-13",
  "end_date": "2026-04-19",
  "responses": [
    {
      "response_id": 10,
      "patient_id": 3,
      "consult_id": 5,
      "response_date": "2026-04-19 20:00:00",
      "adherence": 5,
      "non_compliance": null,
      "difficulty_level": 3,
      "pain_level": 2,
      "progress_perception": "Better",
      "issues": "none",
      "notes": "Feeling better this week"
    }
  ]
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `400`

```json
{
  "error": "end_date query param is required in YYYY-MM-DD format"
}
```

or

```json
{
  "error": "Invalid end_date. Use YYYY-MM-DD"
}
```

## Internal Telegram trigger endpoints

### `POST /internal/send-response-reminders`

Triggers Telegram weekly response reminders for all linked patients by calling the bulk reminder helper. This endpoint is protected. [file:2][file:3]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

None required. Sending `{}` is acceptable.

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Response reminders sent"
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `500`

```json
{
  "error": "Failed to send response reminders",
  "detail": "..."
}
```

### `POST /internal/patients/<patient_id>/send-response-reminders`

Triggers a Telegram response reminder for one patient. In the cleaned rewritten design, this endpoint can accept an optional `consult_id` in the JSON body so the reminder can ask the patient to reply with a consult-specific weekly command. [file:2][file:3]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "consult_id": 5
}
```

The body may also be empty if the reminder does not need to target a specific consult. [file:2]

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Response reminder sent",
  "patient_id": 3,
  "consult_id": 5
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `500`

```json
{
  "error": "Failed to send response reminder",
  "detail": "..."
}
```

### `POST /internal/send-latest-instructions`

Triggers Telegram instruction sends for all linked patients using the latest consult per patient. The sender fetches patient consults and uses the newest consult when no explicit consult ID is supplied. [file:2][file:3]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

None required. Sending `{}` is acceptable.

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Latest instructions sent"
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `500`

```json
{
  "error": "Failed to send latest instructions",
  "detail": "..."
}
```

### `POST /internal/patients/<patient_id>/send-instructions`

Triggers a Telegram instruction send for a single patient. In the cleaned rewritten design, the JSON body can include `consult_id` so a specific consult is used instead of automatically falling back to the latest consult. [file:2][file:3]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

```json
{
  "consult_id": 5
}
```

The body may also be empty if the latest consult should be used. [file:2]

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Instructions sent",
  "patient_id": 3,
  "consult_id": 5
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `500`

```json
{
  "error": "Failed to send instructions",
  "detail": "..."
}
```

### `POST /internal/consults/<consult_id>/send-instructions`

Triggers a Telegram instruction send directly from a consult ID. The endpoint first looks up the consult, then uses its linked `patient_id` to send the consult-specific instruction message. This is the cleanest internal route when Workato already has the consult record. [file:2]

#### Request header

```http
X-API-KEY: <your-api-key>
Content-Type: application/json
```

#### Request body

None required. Sending `{}` is acceptable.

#### Successful JSON response structure

Status: `200`

```json
{
  "message": "Instructions sent",
  "consult_id": 5,
  "patient_id": 3
}
```

#### Unsuccessful JSON response structure

Status: `401`

```json
{
  "error": "Unauthorized"
}
```

Status: `404`

```json
{
  "error": "Consult not found"
}
```

Status: `500`

```json
{
  "error": "Failed to send instructions",
  "detail": "..."
}
```

## Telegram bot integration notes

The Telegram bot links a patient via `/patients/<patient_id>/link-telegram`, looks up the patient through `/patients/by-telegram/<chat_id>`, and submits weekly answers to `/responses` once the questionnaire is completed. In the cleaned rewritten design, the bot can also carry `consult_id` through the weekly response flow so responses are tied to a specific consult instead of only a patient. [file:1][file:2]
