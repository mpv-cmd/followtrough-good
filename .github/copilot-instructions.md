# GitHub Copilot Instructions for FollowThrough

Purpose: Help AI coding agents become productive quickly in this repo by describing architecture, key flows, conventions, and examples.

- Big picture:
  - This is a small FastAPI backend + minimal frontend. The API is in `backend/main.py` which exposes `/upload`, `/latest`, `/auth/google`, and `/approve_bulk`.
  - Upload flow: client POSTs audio to `/upload` -> `transcribe.transcribe_file()` produces text -> `extract_action.extract_actions()` finds action items -> payload written to `uploads/latest.json`.
  - Approve flow: `/approve_bulk` reads `uploads/latest.json`, uses `google_token.json` credentials and `google_calendar.create_event()` to create calendar events. Deduplication uses a key derived from action title + deadline (see `_make_dedupe_key` in `backend/main.py`).

- Key files to inspect first:
  - backend/main.py — entrypoints, safety guard, JSON shape, dedupe logic, and Google auth flow.
  - backend/transcribe.py — speech-to-text helper used by `/upload`.
  - backend/extract_action.py — NLP rule extraction producing action objects.
  - backend/google_calendar.py — OAuth flow (`get_flow`) and `create_event` implementation; token stored in `google_token.json`.
  - backend/uploads/ — stores transcripts and `latest.json` used by the UI and approve flow.

- Important patterns & conventions:
  - Safety guard: `backend/main.py` contains a file-scan that exits if backend .py files contain raw HTML tags. Avoid embedding HTML in backend code.
  - Persistent state: `uploads/latest.json` is the single source of truth for current upload and approval state; any change to approval sets `approved_keys`.
  - Tokens: OAuth credentials are written to `google_token.json` at auth callback.
  - Data shapes: `latest.json` payload contains `actions` (list), `approved_keys` (list of strings), `file_id`, `filename`, and `created_at`.

- Developer flows (how to run locally):
  - Install deps: `pip install -r backend/requirements.txt`
  - Run backend: `uvicorn backend.main:app --reload --port 8000`
  - Open local frontend (if using the static approve HTML) via a simple server (e.g. `npx http-server frontend -p 5500`) to match CORS origins.

- Examples (useful for tests and quick automation):
  - Upload example (curl):
    `curl -F "file=@meeting.mp3" http://127.0.0.1:8000/upload`
  - Approve bulk example (JSON body to `/approve_bulk`):
    `{ "indices": [0,1], "deadlines": { "0": "2026-02-15", "1": "2026-02-20" } }`

- Things to watch / gotchas:
  - If `google_token.json` is missing, `/approve_bulk` returns an error instructing the user to visit `/auth/google`.
  - Deduplication: the system dedupes by `deadline|title` string. If two actions share both, only the first will create an event.
  - Date format: deadlines are simple date strings (ISO-ish). Validate before calling `create_event`.

- How to contribute edits safely:
  - Keep backend free of HTML strings to avoid the safety guard failing on startup (see top of `backend/main.py`).
  - Update `uploads/latest.json` shape in code and tests together.

If anything here is unclear or you'd like more examples (unit tests, sample payloads), tell me which area to expand.
