import os
import shutil
import tempfile
import time
import uuid
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
