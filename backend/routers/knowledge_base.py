from pathlib import Path
import threading
import time
import uuid
from typing import List

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from pydantic import BaseModel

import config
from core.log import get_logger
from core.state import RetrievedPassage
from rag.ingest import load_and_chunk_directory, load_and_chunk_document
from rag.vector_store import get_vector_store

logger = get_logger(__name__)
router = APIRouter()
_INGESTIONS: dict[str, dict] = {}
_INGESTIONS_LOCK = threading.Lock()


class KBStatus(BaseModel):
    total_documents: int
    total_chunks: int
    embedding_model: str
    index_ready: bool
    dimensions: int


class SearchResult(BaseModel):
    query: str
    results: List[RetrievedPassage]


@router.get("/status", response_model=KBStatus)
def kb_status():
    vstore = get_vector_store()
    doc_count = len({d.metadata.get("doc_name") for d in vstore._documents}) if not vstore.is_empty else 0
    total_chunks = len(vstore._documents) if not vstore.is_empty else 0
    return KBStatus(
        total_documents=doc_count,
        total_chunks=total_chunks,
        embedding_model=config.EMBEDDING_MODEL_NAME,
        index_ready=not vstore.is_empty,
        dimensions=config.EMBEDDING_DIMENSION,
    )


@router.post("/upload")
async def upload_kb_documents(files: List[UploadFile] = File(...)):
    """Queue large document ingestion so status can be polled honestly."""
    if not files:
        raise HTTPException(400, detail="No files provided")

    ingestion_id = str(uuid.uuid4())
    stored_files: list[tuple[str, bytes]] = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        stored_files.append((f.filename, await f.read()))
    if not stored_files:
        raise HTTPException(400, detail="No valid PDF documents found in upload")
    with _INGESTIONS_LOCK:
        _INGESTIONS[ingestion_id] = {"id": ingestion_id, "status": "queued", "stage": "queued", "completed_chunks": 0, "total_chunks": 0, "error": None}

    def worker():
        all_chunks = []
        try:
            for index, (filename, content) in enumerate(stored_files, start=1):
                with _INGESTIONS_LOCK:
                    _INGESTIONS[ingestion_id].update({"status": "running", "stage": f"parsing {filename} ({index}/{len(stored_files)})"})
                # Keep the original PDF in the KB source directory.  The
                # vector index is derived data; this retained file is what a
                # later reindex reads.
                safe_name = Path(filename).name
                stored_path = Path(config.KB_STORE_DIR / f"{ingestion_id[:8]}_{safe_name}")
                stored_path.parent.mkdir(parents=True, exist_ok=True)
                stored_path.write_bytes(content)
                chunks = load_and_chunk_document(str(stored_path))
                all_chunks.extend(chunks)
                with _INGESTIONS_LOCK:
                    _INGESTIONS[ingestion_id].update({"stage": "chunking complete", "total_chunks": len(all_chunks)})
            if not all_chunks:
                raise ValueError("Document did not yield any indexable chunks")
            with _INGESTIONS_LOCK:
                _INGESTIONS[ingestion_id]["stage"] = "embedding"
            vstore = get_vector_store()
            # Add one chunk at a time so polling reflects actual completed
            # embeddings, not a fabricated percentage for a long batch.
            added = 0
            for chunk in all_chunks:
                vstore.add_documents([chunk])
                added += 1
                with _INGESTIONS_LOCK:
                    _INGESTIONS[ingestion_id].update({
                        "stage": f"embedding {added}/{len(all_chunks)} chunks",
                        "completed_chunks": added,
                    })
            vstore.save()
            with _INGESTIONS_LOCK:
                _INGESTIONS[ingestion_id].update({"status": "completed", "stage": "done", "completed_chunks": added, "total_chunks": len(all_chunks)})
        except Exception as exc:
            logger.exception("[knowledge-base] ingestion failed")
            with _INGESTIONS_LOCK:
                _INGESTIONS[ingestion_id].update({"status": "failed", "stage": "failed", "error": str(exc)})
    threading.Thread(target=worker, daemon=True, name=f"kb-ingest-{ingestion_id[:8]}").start()
    return {"ingestion_id": ingestion_id, "message": "Ingestion queued"}


@router.get("/ingestions/{ingestion_id}")
def ingestion_status(ingestion_id: str):
    with _INGESTIONS_LOCK:
        status = _INGESTIONS.get(ingestion_id)
        if status is None:
            raise HTTPException(404, detail="Ingestion job not found")
        return dict(status)


@router.delete("/documents/{doc_name:path}")
def remove_document(doc_name: str):
    vstore = get_vector_store()
    if vstore.is_empty:
        return SearchResult(query=query, results=[])

    remaining = [
        d for d in vstore._documents if d.metadata.get("doc_name") != doc_name
    ]
    removed = len(vstore._documents) - len(remaining)
    if removed == 0:
        raise HTTPException(
            404, detail=f"Document '{doc_name}' not found in index"
        )

    vstore._faiss_store = FAISS.from_documents(
        remaining,
        vstore._embeddings,
        distance_strategy=DistanceStrategy.COSINE,
    )
    vstore._documents = remaining
    vstore._bm25_retriever = BM25Retriever.from_documents(remaining)
    vstore._bm25_retriever.k = config.SPARSE_TOP_K
    vstore.save()

    return {
        "message": f"Removed document '{doc_name}' ({removed} chunks)",
        "chunks_removed": removed,
    }


@router.post("/reindex")
def reindex():
    kb_dir = config.KB_DOCS_DIR
    if not kb_dir.exists():
        raise HTTPException(
            404, detail=f"KB docs directory not found: {kb_dir}"
        )

    vstore = get_vector_store()
    chunks = load_and_chunk_directory(str(kb_dir))
    vstore._documents = []
    vstore._faiss_store = None
    vstore._bm25_retriever = None
    if chunks:
        vstore.add_documents(chunks)
    vstore.save()

    return {
        "message": f"Reindexed {len(chunks)} chunks from {kb_dir}",
        "chunks_indexed": len(chunks),
    }


@router.get("/search", response_model=SearchResult)
def search_kb(
    query: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20)
):
    vstore = get_vector_store()
    if vstore.is_empty:
        raise HTTPException(404, detail="Vector store is empty")
    results = vstore.retrieve(query, top_k=top_k)
    return SearchResult(query=query, results=results)
