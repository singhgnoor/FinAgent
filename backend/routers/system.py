from datetime import datetime, timezone

import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from core.llm import get_llm
from core.log import get_logger

logger = get_logger(__name__)
router = APIRouter()

_START_TIME = datetime.now(timezone.utc)

# Explicitly whitelist user-facing tunables: credentials and filesystem paths
# never cross the API boundary.
EDITABLE_CONFIG = {
    "DEFAULT_ALERT_THRESHOLD": (int, 0, 100),
    "LLM_PROVIDER": (str, None, None),
    "LLM_MODEL_NAME": (str, None, None),
    "LLM_TEMPERATURE": (float, 0, 2),
    "TOP_K_DEFAULT": (int, 1, 20),
    "FINAL_TOP_K": (int, 1, 20),
    "EMBEDDING_MODEL_NAME": (str, None, None),
    "DENSE_TOP_K": (int, 1, 100),
    "SPARSE_TOP_K": (int, 1, 100),
    "CONFIDENCE_THRESHOLD": (float, 0, 1),
    "NARRATIVE_CHUNK_TOKENS": (int, 100, 2000),
    "NARRATIVE_CHUNK_OVERLAP_TOKENS": (int, 0, 500),
    "TABLE_CHUNK_MAX_TOKENS": (int, 100, 5000),
    "DENSE_WEIGHT": (float, 0, 1),
    "SPARSE_WEIGHT": (float, 0, 1),
    "RRF_K": (int, 1, 500),
    "RECENCY_HALF_LIFE_DAYS": (int, 1, 3650),
    "RECENCY_WEIGHT": (float, 0, 1),
    "RECENCY_FLOOR": (float, 0, 1),
    "RERANK_MODEL_NAME": (str, None, None),
    "RERANK_CANDIDATE_POOL": (int, 1, 100),
}


def _config_values() -> dict[str, Any]:
    return {name: getattr(config, name) for name in EDITABLE_CONFIG}


def _write_config(updates: dict[str, Any]) -> None:
    """Persist simple constant assignments without evaluating user input."""
    path = config.BASE_DIR / "config.py"
    source = path.read_text(encoding="utf-8")
    for name, value in updates.items():
        rendered = repr(value)
        pattern = rf"(?m)^{re.escape(name)}\s*=\s*.*$"
        updated, count = re.subn(pattern, f"{name} = {rendered}", source, count=1)
        if count != 1:
            raise HTTPException(500, detail=f"Could not persist {name} in config.py")
        source = updated
        setattr(config, name, value)
    path.write_text(source, encoding="utf-8")


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


@router.get("/config")
def get_config():
    return {"values": _config_values(), "editable": list(EDITABLE_CONFIG)}


@router.put("/config")
def update_config(payload: dict[str, Any]):
    updates = payload.get("values", payload)
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(400, detail="Provide one or more configuration values")
    validated: dict[str, Any] = {}
    for name, value in updates.items():
        definition = EDITABLE_CONFIG.get(name)
        if definition is None:
            raise HTTPException(400, detail=f"{name} is not user-editable")
        expected, minimum, maximum = definition
        if expected is str:
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(422, detail=f"{name} must be a non-empty string")
            validated[name] = value.strip()
        else:
            try:
                typed = expected(value)
            except (TypeError, ValueError):
                raise HTTPException(422, detail=f"{name} has an invalid value")
            if minimum is not None and not minimum <= typed <= maximum:
                raise HTTPException(422, detail=f"{name} must be between {minimum} and {maximum}")
            validated[name] = typed
    _write_config(validated)
    # Retrieval settings are read from ``config`` per request.  Recreate the
    # cached LLM so model/temperature changes affect the next signal too.
    if {"LLM_MODEL_NAME", "LLM_TEMPERATURE", "LLM_PROVIDER"} & set(validated):
        import core.llm
        core.llm._llm = None
    return {"values": _config_values(), "message": "Configuration saved and applied to subsequent requests"}
