# RAG Gemini Chatbot (FastAPI + Static Frontend)

A lightweight RAG-style chatbot that indexes Freshservice API docs and answers questions using a local Chroma collection and an LLM. The project ships with a FastAPI backend and a static HTML/CSS/JS frontend. You can run both together on one port or split them across two ports to avoid confusion.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [Run Modes](#run-modes)
  - [Single-port (frontend + backend)](#single-port-frontend--backend)
  - [Two-port (split frontend and backend)](#two-port-split-frontend-and-backend)
- [API Endpoints](#api-endpoints)
- [Frontend Configuration](#frontend-configuration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Deployment Notes](#deployment-notes)
- [Security & Limits](#security--limits)
- [Acknowledgements](#acknowledgements)

## Features
- FastAPI backend serving JSON and SSE streaming responses.
- Static frontend with responsive UI, quick replies, and live streaming display.
- RAG workflow backed by a local Chroma persistent client (initialized by `assistant.py`).
- Simple rate limit middleware for `/api/*` endpoints.
- Configurable backend base URL for cross-origin frontend calls.

## Architecture
- Backend (`app.py`)
  - Initializes Chroma via `assistant.init_chroma(rebuild=False)` on startup.
  - Serves `/api/chat` and `/api/chat/stream` (SSE) for Q&A.
  - Optionally serves static assets and root UI when `BACKEND_ONLY=0`.
  - CORS configured via `ALLOWED_ORIGINS` so a separate frontend can call the backend.
- Frontend (`static/`)
  - Plain HTML/CSS/JS served statically.
  - `app.js` uses `window.__API_BASE__` to call the backend and `window.__ASSET_BASE__` for images.
  - Streams responses from `/api/chat/stream` and falls back to `/api/chat`.

## Project Structure
```
LINKEYE_ASSESSMENT_CHATBOT/
├── app.py                         # FastAPI app, CORS, SSE, static mounts
├── assistant.py                   # Chroma/embedding logic and query functions
├── data/processed/tickets_static.json
├── freshservice_static_scraper.py # Optional scraper/util
├── images/                        # Static image assets
│   ├── Interstellar wallpaper 4k.jpg
│   ├── about_avatar.jpg
│   └── logo.png
├── static/                        # Frontend
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── requirements.txt
└── README.md
```

## Prerequisites
- Python 3.9+ recommended
- `pip` for dependency installation

## Setup
```powershell
# From project root
pip install -r requirements.txt
```

## Environment Variables
| Name | Default | Purpose |
|------|---------|---------|
| `BACKEND_ONLY` | `0` | `1` disables static mounts; backend API only. |
| `ALLOWED_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Comma-separated origins allowed by CORS. Add `http://127.0.0.1:8001` when splitting ports. |
| `MAX_QUESTION_CHARS` | `512` | Rejects questions longer than this. |
| `RATE_LIMIT_MAX_PER_MIN` | `60` | Max requests per IP per minute for `/api/*`. |

## Run Modes

### Single-port (frontend + backend)
- Runs both API and static UI on port `8000`.
```powershell
$env:BACKEND_ONLY="0"; uvicorn app:app --host 127.0.0.1 --port 8000 --reload
# Open: http://127.0.0.1:8000/
```

### Two-port (split frontend and backend)
- Backend on `8000`, frontend on `8001`.
```powershell
# Terminal A (project root): backend-only API
$env:BACKEND_ONLY="1";
$env:ALLOWED_ORIGINS="http://127.0.0.1:8001,http://localhost:8001,http://127.0.0.1:8000,http://localhost:8000";
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Terminal B (static folder): frontend
cd .\static
python -m http.server 8001

# Open the app (frontend calls backend via query params):
http://127.0.0.1:8001/?api=http://127.0.0.1:8000&assets=http://127.0.0.1:8000
```

## API Endpoints
- `POST /api/chat`
  - Body: `{ "question": "..." }`
  - Returns: `{ "answer": string, "matches": [...] }`
- `POST /api/chat/stream`
  - SSE stream of the answer text in chunks, ends with `[DONE]`.

Example (PowerShell):
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/chat" -Method POST -ContentType application/json -Body '{"question":"List Freshservice endpoints"}' | ConvertTo-Json
```

## Frontend Configuration
- `index.html` reads query params to configure cross-origin:
  - `api`: backend base (e.g., `http://127.0.0.1:8000`)
  - `assets`: asset base (images); defaults to `api` when omitted
- `app.js` defines:
  - `API_BASE = window.__API_BASE__ || ''`
  - Uses `API_BASE` for `/api/chat` and `/api/chat/stream`
  - Sets avatar image from `ASSET_BASE`

## Testing
1. Start backend-only (port `8000`) and frontend (port `8001`) as shown above.
2. Verify backend directly:
   ```powershell
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/chat" -Method POST -ContentType application/json -Body '{"question":"List Freshservice endpoints"}' | ConvertTo-Json
   ```
3. Verify frontend static server:
   ```powershell
   Invoke-WebRequest -Uri "http://127.0.0.1:8001/" -UseBasicParsing | Select-Object -ExpandProperty StatusCode
   Invoke-WebRequest -Uri "http://127.0.0.1:8001/app.js" -UseBasicParsing | Select-Object -ExpandProperty StatusCode
   Invoke-WebRequest -Uri "http://127.0.0.1:8001/styles.css" -UseBasicParsing | Select-Object -ExpandProperty StatusCode
   ```
4. Open the app:
   - `http://127.0.0.1:8001/?api=http://127.0.0.1:8000&assets=http://127.0.0.1:8000`
   - Ask a question; you should see streaming output. If streaming fails, the frontend falls back to JSON.

## Troubleshooting
- CORS blocked:
  - Ensure `ALLOWED_ORIGINS` includes your frontend origin (`http://127.0.0.1:8001`).
- Frontend not loading images:
  - Confirm `assets` query param points to the backend serving `/images` (or run full mode on a single port).
- SSE not streaming:
  - Some proxies/browsers may buffer SSE; test in a local environment, or use the JSON fallback.
- “Question too long”:
  - Adjust `MAX_QUESTION_CHARS`.
- Rate limit (HTTP 429):
  - Reduce request frequency or increase `RATE_LIMIT_MAX_PER_MIN`.

## Deployment Notes
- Production typically runs backend behind a reverse proxy (e.g., Nginx) and serves the frontend separately.
- Example Nginx snippet (proxy API to Uvicorn on `8000` and serve static UI):
```nginx
server {
    listen 80;
    server_name example.com;

    location /api/ {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        root /var/www/rag_ui;  # folder containing static/index.html
        try_files $uri $uri/ /index.html;
    }
}
```

## Security & Limits
- Per-IP rate limiting on `/api/*` requests (defaults to 60/min).
- Input length guard via `MAX_QUESTION_CHARS`.
- Consider authentication and stricter CORS for production.

## Acknowledgements
- FastAPI, Uvicorn
- Chroma for local vector storage
- Freshservice documentation (source for static dataset)