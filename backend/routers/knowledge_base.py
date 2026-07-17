from pathlib import Path
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
    doc_count = len(vstore._documents) if not vstore.is_empty else 0
    total_chunks = len(vstore._documents) if not vstore.is_empty else 0
    return KBStatus(
        total_documents=doc_count,
        total_chunks=total_chunks,
        embedding_model=config.EMBEDDING_MODEL_NAME,
        index_ready=True,
        dimensions=config.EMBEDDING_DIMENSION,
    )


@router.post("/upload")
async def upload_kb_documents(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, detail="No files provided")

    all_chunks = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        tmp_path = Path(config.DATA_DIR / "_upload_tmp" / Path(f.filename).name)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        content = await f.read()
        tmp_path.write_bytes(content)
        try:
            chunks = load_and_chunk_document(str(tmp_path))
            all_chunks.extend(chunks)
        finally:
            tmp_path.unlink(missing_ok=True)

    if not all_chunks:
        raise HTTPException(400, detail="No valid PDF documents found in upload")

    vstore = get_vector_store()
    added = vstore.add_documents(all_chunks)
    vstore.save()

    return {
        "message": f"Added {added} chunks from {len(files)} documents",
        "chunks_added": added,
    }


@router.delete("/documents/{doc_name:path}")
def remove_document(doc_name: str):
    vstore = get_vector_store()
    if vstore.is_empty:
        raise HTTPException(404, detail="Vector store is empty")

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
