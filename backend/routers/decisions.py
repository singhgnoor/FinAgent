from fastapi import APIRouter, HTTPException

import config
from core.log import get_logger
from core.json_store import read_json_list

logger = get_logger(__name__)
router = APIRouter()

DECISIONS_FILE = config.DATA_DIR / "decisions_history.json"


@router.get("/")
def list_decisions(page: int = 1, page_size: int = 20, asset: str | None = None, alerted: bool | None = None):
    if not DECISIONS_FILE.exists():
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
    all_decisions = read_json_list(DECISIONS_FILE)
    if asset:
        all_decisions = [item for item in all_decisions if asset.lower() in item.get("asset", "").lower()]
    if alerted is not None:
        all_decisions = [item for item in all_decisions if bool(item.get("alert_triggered")) == alerted]
    all_decisions.sort(key=lambda item: item.get("created_at", ""), reverse=True)

    total = len(all_decisions)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = all_decisions[start:start + page_size]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


@router.get("/{artefact_id}")
def get_decision(artefact_id: str):
    if not DECISIONS_FILE.exists():
        raise HTTPException(404, detail="No decisions found")
    data = read_json_list(DECISIONS_FILE)
    for d in data:
        if d.get("artefact_id") == artefact_id:
            return d
    raise HTTPException(404, detail=f"Decision '{artefact_id}' not found")
