import os
import shutil
import tempfile
import time
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import config
from backend.models.requests import NewsRequest, PriceTickRequest, SignalRequest
from backend.models.responses import PipelineResponse
from core.graph import run_once
from core.log import get_logger
from core.state import RawSignal, SignalType
from core.json_store import update_json_list

logger = get_logger(__name__)
router = APIRouter()

DECISIONS_FILE = config.DATA_DIR / "decisions_history.json"
SIGNALS_FILE = config.DATA_DIR / "signals_history.json"
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _persist_decision(artefact, state) -> None:
    if artefact is None:
        return
    os.makedirs(config.DATA_DIR, exist_ok=True)
    record = artefact.model_dump(mode="json")
    record.update({
        "trace_log": [item.model_dump(mode="json") for item in state.get("trace_log", [])],
        "errors": state.get("errors", []),
        "hypothesis": state.get("hypothesis").model_dump(mode="json") if state.get("hypothesis") else None,
        "retrieved_passages": [item.model_dump(mode="json") for item in state.get("retrieved_passages", [])],
        "normalized_event": state.get("normalized_event").model_dump(mode="json") if state.get("normalized_event") else None,
    })
    update_json_list(DECISIONS_FILE, lambda items: items.append(record))


def _persist_signal(raw_signal: RawSignal, state) -> None:
    event = state.get("normalized_event")
    if event is None:
        return
    record = event.model_dump(mode="json")
    record["raw_id"] = raw_signal.raw_id
    update_json_list(SIGNALS_FILE, lambda items: items.append(record))


def _run_pipeline(
    raw_signal: RawSignal, alert_threshold: int = 70
) -> PipelineResponse:
    start = time.perf_counter()
    try:
        state = run_once(raw_signal, alert_threshold=alert_threshold)
        elapsed = (time.perf_counter() - start) * 1000
        artefact = state.get("artefact")
        _persist_signal(raw_signal, state)
        _persist_decision(artefact, state)
        return PipelineResponse(
            success=True,
            signal_id=raw_signal.raw_id,
            normalized_event=state.get("normalized_event"),
            retrieved_passages=state.get("retrieved_passages", []),
            hypothesis=state.get("hypothesis"),
            decision=artefact,
            trace_log=state.get("trace_log", []),
            errors=state.get("errors", []),
            elapsed_ms=round(elapsed, 2),
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception("[signals] Pipeline error: %s", e)
        return PipelineResponse(
            success=False,
            signal_id=raw_signal.raw_id,
            errors=[str(e)],
            elapsed_ms=round(elapsed, 2),
        )


def _state_snapshot(state) -> dict:
    """JSON-safe incremental view used by the polling UI."""
    def dump(value):
        return value.model_dump(mode="json") if value is not None else None
    return {
        "normalized_event": dump(state.get("normalized_event")),
        "retrieved_passages": [dump(item) for item in state.get("retrieved_passages", [])],
        "hypothesis": dump(state.get("hypothesis")),
        "decision": dump(state.get("artefact")),
        "trace_log": [dump(item) for item in state.get("trace_log", [])],
        "errors": list(state.get("errors", [])),
    }


def _start_job(raw_signal: RawSignal, alert_threshold: int = 70) -> str:
    """Run LangGraph in a worker and retain each graph-state transition.

    `stream(..., values)` is deliberate: it exposes the actual state emitted
    after every agent instead of manufacturing client-side progress.
    """
    job_id = str(uuid.uuid4())
    with _JOBS_LOCK:
        _JOBS[job_id] = {"job_id": job_id, "signal_id": raw_signal.raw_id, "status": "queued", "stage": "queued", "result": None, "error": None, "created_at": datetime.now(timezone.utc).isoformat()}

    def worker():
        started = time.perf_counter()
        try:
            from core.graph import get_compiled_graph
            from core.state import create_initial_state
            initial = create_initial_state(alert_threshold=alert_threshold)
            initial["raw_signal"] = raw_signal
            final_state = initial
            for state in get_compiled_graph().stream(initial, stream_mode="values"):
                final_state = state
                trace = state.get("trace_log", [])
                stage = trace[-1].agent.value if trace else "ingestion_agent"
                with _JOBS_LOCK:
                    _JOBS[job_id].update({"status": "running", "stage": stage, "result": _state_snapshot(state)})
            artefact = final_state.get("artefact")
            _persist_signal(raw_signal, final_state)
            _persist_decision(artefact, final_state)
            with _JOBS_LOCK:
                _JOBS[job_id].update({"status": "completed", "stage": "completed", "result": _state_snapshot(final_state), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})
        except Exception as exc:
            logger.exception("[signals] streamed pipeline error")
            with _JOBS_LOCK:
                _JOBS[job_id].update({"status": "failed", "stage": "failed", "error": str(exc), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})

    threading.Thread(target=worker, daemon=True, name=f"finagent-job-{job_id[:8]}").start()
    return job_id


@router.post("/process", response_model=PipelineResponse)
def process_signal(req: SignalRequest):
    raw = RawSignal(
        raw_id=str(uuid.uuid4()),
        signal_type=SignalType(req.signal_type),
        source=req.source,
        payload=req.payload,
        received_at=datetime.now(timezone.utc),
    )
    return _run_pipeline(raw)


@router.post("/price-tick", response_model=PipelineResponse)
def process_price_tick(req: PriceTickRequest):
    raw = RawSignal(
        raw_id=str(uuid.uuid4()),
        signal_type=SignalType.PRICE_TICK,
        source="api",
        payload=req.model_dump(),
        received_at=datetime.now(timezone.utc),
    )
    return _run_pipeline(raw)


@router.post("/price-tick/jobs")
def process_price_tick_job(req: PriceTickRequest):
    raw = RawSignal(raw_id=str(uuid.uuid4()), signal_type=SignalType.PRICE_TICK, source="api", payload=req.model_dump(mode="json"), received_at=datetime.now(timezone.utc))
    return {"job_id": _start_job(raw), "signal_id": raw.raw_id}


@router.post("/news/jobs")
def process_news_job(req: NewsRequest):
    raw = RawSignal(raw_id=str(uuid.uuid4()), signal_type=SignalType.NEWS_TEXT, source="api", payload=req.model_dump(exclude_none=True, mode="json"), received_at=datetime.now(timezone.utc))
    return {"job_id": _start_job(raw), "signal_id": raw.raw_id}


@router.get("/jobs/latest")
def get_latest_job():
    """Expose the most recently created job so the dashboard can reflect live work."""
    with _JOBS_LOCK:
        if not _JOBS:
            return {"job": None}
        job = max(_JOBS.values(), key=lambda item: item.get("created_at", ""))
        return {"job": dict(job)}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, detail="Pipeline job not found")
        return dict(job)


@router.get("/market-data/{ticker}")
def get_market_data(ticker: str):
    """Use the existing yFinance integration to populate the OHLCV form."""
    from core.ingestion_manager import fetch_live_yfinance_tick
    raw = fetch_live_yfinance_tick(ticker)
    if raw is None:
        raise HTTPException(404, detail=f"No recent yFinance data for {ticker.upper()}; enter OHLCV manually.")
    return {"ticker": ticker.upper(), "source": raw.source, **raw.payload}


@router.post("/news", response_model=PipelineResponse)
def process_news(req: NewsRequest):
    raw = RawSignal(
        raw_id=str(uuid.uuid4()),
        signal_type=SignalType.NEWS_TEXT,
        source="api",
        payload=req.model_dump(exclude_none=True),
        received_at=datetime.now(timezone.utc),
    )
    return _run_pipeline(raw)


@router.post("/document", response_model=PipelineResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("filing"),
    source: str = Form("api"),
    asset: str | None = Form(None),
    alert_threshold: int = Form(70),
):
    if not file.filename:
        raise HTTPException(400, detail="No file provided")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        from rag.ingest import load_and_chunk_document

        chunks = load_and_chunk_document(tmp_path, asset=asset)
        if not chunks:
            raise HTTPException(400, detail="Document did not yield any indexable chunks")
        from rag.vector_store import get_vector_store
        vstore = get_vector_store()
        indexed = vstore.add_documents(chunks)
        vstore.save()
        excerpt = chunks[0].page_content[:2000] if chunks else ""

        raw = RawSignal(
            raw_id=str(uuid.uuid4()),
            signal_type=SignalType.DOCUMENT,
            source=source,
            payload={
                "doc_name": file.filename,
                "doc_type": doc_type,
                "excerpt": excerpt,
                "asset": asset,
            },
            received_at=datetime.now(timezone.utc),
        )
        response = _run_pipeline(raw, alert_threshold=alert_threshold)
        response.chunks_indexed = indexed
        response.embedding_completed = indexed == len(chunks)
        return response
    finally:
        os.unlink(tmp_path)


@router.get("/recent")
def list_recent_signals(limit: int = 20):
    """Raw normalized feed, independent of whether a decision was emitted."""
    from core.json_store import read_json_list
    safe_limit = max(1, min(limit, 100))
    events = read_json_list(SIGNALS_FILE)
    events.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return {"items": events[:safe_limit], "total": len(events)}
