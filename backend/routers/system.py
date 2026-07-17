from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

import config
from core.llm import get_llm
from core.log import get_logger

logger = get_logger(__name__)
router = APIRouter()

_START_TIME = datetime.now(timezone.utc)


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    services: dict[str, bool]
    checks: dict[str, str]


class StatusResponse(BaseModel):
    status: str
    llm_configured: bool
    llm_model: str
    embedding_model: str
    vector_store_ready: bool
    document_count: int
    pipeline_available: bool
    uptime_seconds: float


@router.get("/health", response_model=HealthResponse)
def health():
    llm_ok = bool(config.OPENAI_API_KEY)
    try:
        get_llm()
    except Exception:
        llm_ok = False

    vs_ok = False
    try:
        from rag.vector_store import get_vector_store
        get_vector_store()
        vs_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        services={"llm": llm_ok, "vector_store": vs_ok, "api": True},
        checks={"llm": "ok" if llm_ok else "error", "vector_store": "ok" if vs_ok else "error"},
    )


@router.get("/status", response_model=StatusResponse)
def system_status():
    llm_ok = bool(config.OPENAI_API_KEY)
    try:
        get_llm()
    except Exception:
        llm_ok = False

    vs_ok = False
    doc_count = 0
    try:
        from rag.vector_store import get_vector_store
        vs = get_vector_store()
        vs_ok = True
        doc_count = len(vs._documents) if not vs.is_empty else 0
    except Exception:
        pass

    uptime = (datetime.now(timezone.utc) - _START_TIME).total_seconds()

    return StatusResponse(
        status="ok",
        llm_configured=llm_ok,
        llm_model=config.LLM_MODEL_NAME,
        embedding_model=config.EMBEDDING_MODEL_NAME,
        vector_store_ready=vs_ok,
        document_count=doc_count,
        pipeline_available=llm_ok,
        uptime_seconds=round(uptime, 2),
    )
