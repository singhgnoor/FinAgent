# FinAgent

=== 1. PROJECT OVERVIEW ===
FinAgent is a multi-agent, LangGraph-orchestrated, RAG-grounded investment decision system, built to fulfill the Mock Inter IIT Problem Statement. It ingests financial signals (live market data or historical CSVs), grounds them in context from a local knowledge base, analyzes market hypotheses, and synthesizes a final, confidence-scored trading decision.

**Tech Stack:**
- **Orchestration:** LangChain, LangGraph
- **Vector Store:** FAISS (with BM25 for sparse/hybrid search)
- **Embedding Model:** `FinLang/finance-embeddings-investopedia` (via sentence-transformers)
- **LLM Backbone:** OpenAI (`gpt-5.4-mini` configured via `.env`)
- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite, styled with TailwindCSS

=== 2. ARCHITECTURE ===
The system uses a 4-agent sequential pipeline connected via LangGraph shared state:
1. **Ingestion Agent**: Normalizes raw unstructured or semi-structured signals from the market.
2. **Retrieval Agent**: Performs asset-scoped, hybrid retrieval (dense + sparse) with Reciprocal Rank Fusion and cross-encoder reranking.
3. **Analysis Agent**: Classifies the signal, generates hypotheses, and applies a confidence score based on the retrieved financial context.
4. **Decision Agent**: Synthesizes the analysis into an actionable artefact, detects contradictions, and triggers alerts if necessary.

```text
[Market Feed] --> (Ingestion) --> [State] --> (Retrieval) --> [State] --> (Analysis) --> [State] --> (Decision) --> [UI/Alerts]
                        ^                               |
                        |                               v
                 [Knowledge Base] <================ [FAISS / BM25]
```

=== 3. FOLDER STRUCTURE ===
- **`agents/`**: Contains the four LangGraph node implementations.
  - `ingestion.py` — parses and normalizes signals.
  - `retrieval.py` — RAG query handling, asset-scoped filtering, and score fusion.
  - `analysis.py` — signal classification, hypothesis generation, and confidence scoring.
  - `decision.py` — artefact synthesis, contradiction detection, and alerting.
- **`backend/`**: FastAPI backend application.
  - `routers/` — API endpoints for `decisions`, `knowledge_base`, `signals`, and `system`.
  - `models/` — Pydantic request/response schema definitions.
  - `main.py` — FastAPI app setup, CORS configuration, and router inclusion.
- **`core/`**: Shared core logic, logging, and LangGraph definitions.
  - `state.py` — schema for the shared LangGraph state.
  - `graph.py` — LangGraph pipeline assembly and execution logic.
  - `log.py` — system-wide observability and logging setup.
  - `ingestion_manager.py` — fetches live yfinance ticks or streams CSV data.
- **`data/`**: Local storage directory.
  - `vector_store/` — persisted FAISS indexes and document pickles.
  - `kb_store/` — source of truth for user-uploaded PDF knowledge base files.
- **`frontend/`**: React/Vite Single Page Application.
  - `src/pages/` and `src/components/` — UI views and reusable React components.
  - `src/services/` — API integration and Axios client setup.
- **`rag/`**: Retrieval-Augmented Generation implementation.
  - `ingest.py` — PDF parsing and chunking logic.
  - `vector_store.py` — hybrid retrieval, fusion, and reranking mechanisms.
- **`tests/`**: Automated testing suite.
  - `test_agent_pipeline.py` — end-to-end tests for the agentic pipeline.

=== 4. SETUP / HOW TO RUN ===
**Prerequisites:**
- Python 3.9+
- Node.js (v18+)

**Environment Variables:**
Create a `.env` file in the project root and add your OpenAI API Key:
```env
OPENAI_API_KEY=your-api-key-here
```

**Running the Application (One-Click):**
If you are on Windows, you can launch both backend and frontend servers simultaneously using the provided script:
```powershell
.\run.ps1
```

**Running Manually:**
1. **Backend Setup:**
   ```bash
   python -m venv .venv
   # Windows: .\.venv\Scripts\activate
   # Linux/Mac: source .venv/bin/activate
   pip install -r requirements.txt
   
   # Run backend on port 5174 (default)
   uvicorn backend.main:app --host 127.0.0.1 --port 5174 --reload
   ```

2. **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   
   # Run frontend dev server on port 5173
   npm run dev
   ```
   *Note: The frontend proxy is configured in `vite.config.ts` to forward `/api` requests to `http://localhost:5174`.*

3. **Running the Pipeline from CLI:**
   You can also test ingestion through the CLI:
   ```bash
   python main.py
   ```

4. **Running Tests:**
   ```bash
   pytest tests/
   ```

**First-Run Steps for Evaluators:**
1. Start the application (using `.\run.ps1` or manual commands).
2. Open your browser to `http://localhost:5173`.
3. Navigate to the Knowledge Base section and upload a sample financial PDF report.
4. Navigate to the Signals or Dashboard view, submit a ticker (e.g., TCS or INFY) or a raw signal, and watch the pipeline process it end-to-end.

=== 5. KEY FEATURES MAPPED TO PS REQUIREMENTS ===
| Problem Statement Requirement | Code Location / Implementation |
|-------------------------------|--------------------------------|
| **Ingestion Agent** | `agents/ingestion.py`, `core/ingestion_manager.py` (yfinance / CSV handling) |
| **Retrieval Agent (RAG)** | `agents/retrieval.py`, `rag/vector_store.py` (FAISS, BM25, Reciprocal Rank Fusion) |
| **Analysis Agent** | `agents/analysis.py` (LLM hypotheses + confidence scoring) |
| **Decision Agent** | `agents/decision.py` (Final artefact, alert generation) |
| **Orchestration** | `core/graph.py` (LangGraph state and node wiring) |
| **Observability** | `core/log.py`, outputs to the `logs/` directory |
| **User Interface** | `frontend/` directory (React + Vite SPA) |

=== 6. KNOWN LIMITATIONS ===
- **No Live Trading:** As explicitly out of scope per the PS, the system generates actionable trading recommendations but does not execute them on broker APIs.
- **No Code-Execution Agent:** Python code execution is out of scope; analysis is strictly LLM and RAG driven.
- **Config Requirements:** An OpenAI API key must be supplied in `.env` by the evaluator before the system will function. The Investopedia embedding model downloads on first run, which may cause a brief initial delay.

=== 7. TEAM ===
- Gurnoor Singh
- Parv Singla
- Anubhav
