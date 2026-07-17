import json
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

logger = get_logger(__name__)
router = APIRouter()

DECISIONS_FILE = config.DATA_DIR / "decisions_history.json"


def _persist_decision(artefact) -> None:
    if artefact is None:
        return
    os.makedirs(config.DATA_DIR, exist_ok=True)
    decisions = []
    if DECISIONS_FILE.exists():
        try:
            decisions = json.loads(DECISIONS_FILE.read_text())
        except (json.JSONDecodeError, Exception):
            decisions = []
    decisions.append(json.loads(artefact.model_dump_json()))
    DECISIONS_FILE.write_text(json.dumps(decisions, indent=2, default=str))


def _run_pipeline(
    raw_signal: RawSignal, alert_threshold: int = 70
) -> PipelineResponse:
    start = time.perf_counter()
    try:
        state = run_once(raw_signal, alert_threshold=alert_threshold)
        elapsed = (time.perf_counter() - start) * 1000
        artefact = state.get("artefact")
        _persist_decision(artefact)
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

        chunks = load_and_chunk_document(tmp_path)
        excerpt = chunks[0].page_content[:2000] if chunks else ""

        raw = RawSignal(
            raw_id=str(uuid.uuid4()),
            signal_type=SignalType.DOCUMENT,
            source=source,
            payload={
                "doc_name": file.filename,
                "doc_type": doc_type,
                "excerpt": excerpt,
            },
            received_at=datetime.now(timezone.utc),
        )
        return _run_pipeline(raw, alert_threshold=alert_threshold)
    finally:
        os.unlink(tmp_path)
