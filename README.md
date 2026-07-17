# FinAgent

Multi-agent AI trading system with a FastAPI backend and React frontend.

## Prerequisites

- Python 3.14+
- Node.js 20+
- `.venv\` virtual environment with dependencies installed
- `frontend\node_modules\` installed (`cd frontend && npm install`)

## Running

### Quick start (single command)

Set your OpenAI API key, then run:

```powershell
$env:OPENAI_API_KEY = "sk-proj-..."
.\run.ps1
```

Or set it as a persistent environment variable. The script starts both servers, waits for the backend to be ready, then opens the browser.

### Manual start

#### 1. Backend (port 5174)

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --port 5174 --log-level error
```

#### 2. Frontend (port 5173)

```powershell
cd frontend
npx vite --port 5173
```

#### 3. Open the app

Navigate to **http://localhost:5173** in your browser.

The Vite dev server proxies `/api/*` requests to the backend at `http://localhost:5174`.

## API Endpoints (12 total)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/status` | Full system status (LLM, embedding, uptime) |
| POST | `/api/v1/signals/price-tick` | Ingest a price tick |
| POST | `/api/v1/signals/news` | Ingest a news headline |
| POST | `/api/v1/signals/process` | Generic signal processing |
| POST | `/api/v1/signals/document` | Document ingestion |
| GET | `/api/v1/knowledge-base/status` | Vector store status |
| GET | `/api/v1/knowledge-base/search` | Search knowledge base |
| POST | `/api/v1/knowledge-base/upload` | Upload a document |
| POST | `/api/v1/knowledge-base/reindex` | Reindex all documents |
| DELETE | `/api/v1/knowledge-base/documents/{name}` | Delete a document |
| GET | `/api/v1/decisions/` | List all decisions |
| GET | `/api/v1/decisions/{artefact_id}` | Get a specific decision |

## Integration Tests

```powershell
.venv\Scripts\python.exe test_integration.py
```

Starts the backend, hits all endpoints with strict timeouts, and reports pass/fail.
