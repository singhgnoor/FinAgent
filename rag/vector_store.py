"""
FinAgent — RAG Vector Store & Hybrid Retrieval

Implements the 2.2 requirement (chunk+embed into an open-source vector
store, accept natural-language queries, return top-k passages with source
attribution) with three finance-specific additions on top of plain dense
retrieval:

  1. Hybrid retrieval (dense FAISS + sparse BM25), fused with Reciprocal
     Rank Fusion. Pure dense retrieval misses exact-match tokens that
     matter in finance — tickers, dollar figures, fiscal quarters — since
     embedding models compress exactly those tokens away. BM25 catches
     them; dense catches paraphrase/semantic matches. RRF fuses the two
     ranked lists by RANK POSITION rather than raw score, which sidesteps
     the fact that cosine similarity and BM25 scores live on incompatible
     scales.
  2. Recency-weighted scoring. An 8-month-old earnings call shouldn't
     outrank yesterday's filing purely because it's a marginally better
     semantic match — recency is blended into the final score (not left
     purely semantic), with a floor so old reference docs (e.g. a 10-K)
     never get discounted into irrelevance.
  3. Optional cross-encoder reranking on the fused+recency-weighted
     candidate pool. RRF never looks at query and passage together; a
     cross-encoder is the one component that does, and gives one
     calibrated relevance score to finalize ordering. Feature-flagged via
     config since it costs latency.

Uses LangChain components throughout (FAISS, BM25Retriever, HuggingFace
embeddings, HuggingFace cross-encoder) per the "LangChain for agent
tooling" requirement, rather than hand-rolled retrieval clients.
"""

import os
import pickle
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

import config
from core.state import RetrievedPassage

try:
    from langchain_community.cross_encoders import HuggingFaceCrossEncoder
    _CROSS_ENCODER_AVAILABLE = True
except ImportError:  # optional dependency — reranking degrades gracefully without it
    _CROSS_ENCODER_AVAILABLE = False


class FinAgentVectorStore:
    """
    Wraps a FAISS dense index + BM25 sparse index over the same document
    corpus, and exposes one `retrieve()` method that does hybrid fusion,
    recency weighting, and optional reranking end to end.
    """

    def __init__(self):
        self._embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": config.EMBEDDING_DEVICE},
        )
        self._faiss_store: Optional[FAISS] = None
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._documents: List[Document] = []

        self._cross_encoder = None
        if config.ENABLE_RERANKING and _CROSS_ENCODER_AVAILABLE:
            self._cross_encoder = HuggingFaceCrossEncoder(model_name=config.RERANK_MODEL_NAME)

    @property
    def is_empty(self) -> bool:
        return self._faiss_store is None

    # -- ingestion -----------------------------------------------------

    def add_documents(self, documents: List[Document]) -> int:
        """Embed and index a batch of chunks (from rag/ingest.py). Returns chunks added."""
        if not documents:
            return 0

        if self._faiss_store is None:
            self._faiss_store = FAISS.from_documents(documents, self._embeddings)
        else:
            self._faiss_store.add_documents(documents)

        self._documents.extend(documents)
        # BM25 has no incremental add in LangChain, so rebuild from the full
        # corpus. Fine at knowledge-base-ingestion cadence (uploads), not
        # meant for a high-frequency-write workload.
        self._bm25_retriever = BM25Retriever.from_documents(self._documents)
        self._bm25_retriever.k = config.SPARSE_TOP_K

        return len(documents)

    # -- persistence -----------------------------------------------------

    def save(self, path: str = config.VECTOR_STORE_DIR) -> None:
        if self._faiss_store is None:
            raise ValueError("Nothing to save — no documents have been indexed yet.")
        os.makedirs(path, exist_ok=True)
        self._faiss_store.save_local(path)
        with open(os.path.join(path, "documents.pkl"), "wb") as f:
            pickle.dump(self._documents, f)

    def load(self, path: str = config.VECTOR_STORE_DIR) -> bool:
        """Returns True if an existing index was found on disk and loaded."""
        index_file = os.path.join(path, "index.faiss")
        docs_file = os.path.join(path, "documents.pkl")
        if not (os.path.exists(index_file) and os.path.exists(docs_file)):
            return False

        # allow_dangerous_deserialization: safe here because this only ever
        # loads an index this same app previously saved, never a third-party file.
        self._faiss_store = FAISS.load_local(
            path, self._embeddings, allow_dangerous_deserialization=True
        )
        with open(docs_file, "rb") as f:
            self._documents = pickle.load(f)
        self._bm25_retriever = BM25Retriever.from_documents(self._documents)
        self._bm25_retriever.k = config.SPARSE_TOP_K
        return True

    # -- retrieval -----------------------------------------------------

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievedPassage]:
        """
        Hybrid dense+sparse retrieval, fused with RRF, reweighted by
        recency, optionally reranked, and returned as RetrievedPassage
        objects ready to drop into FinAgentState.
        """
        top_k = top_k or config.FINAL_TOP_K

        if self._faiss_store is None or self._bm25_retriever is None:
            return []

        dense_docs = self._faiss_store.similarity_search(query, k=config.DENSE_TOP_K)
        sparse_docs = self._bm25_retriever.invoke(query)

        fused = self._reciprocal_rank_fusion(dense_docs, sparse_docs)
        scored = self._apply_recency_weighting(fused)
        scored.sort(key=lambda pair: pair[1], reverse=True)

        pool_size = config.RERANK_CANDIDATE_POOL if self._cross_encoder else top_k
        candidate_pool = scored[:pool_size]

        if self._cross_encoder:
            candidate_pool = self._rerank(query, candidate_pool)

        final = candidate_pool[:top_k]
        return [self._to_retrieved_passage(doc, score) for doc, score in final]

    # -- internal helpers ------------------------------------------------

    @staticmethod
    def _reciprocal_rank_fusion(
        dense_docs: List[Document], sparse_docs: List[Document], rrf_k: int = None
    ) -> dict:
        """
        Combines two ranked lists into one score per unique chunk using
        Reciprocal Rank Fusion: score(d) = sum(weight / (rrf_k + rank + 1))
        over every retriever d appeared in. Works on RANK POSITION, not raw
        score, which is what lets us combine cosine similarity and BM25's
        unbounded term-frequency score without calibrating either one.
        """
        rrf_k = rrf_k if rrf_k is not None else config.RRF_K
        scores: dict = {}

        def _accumulate(doc_list: List[Document], weight: float):
            for rank, doc in enumerate(doc_list):
                key = _document_key(doc)
                contribution = weight / (rrf_k + rank + 1)
                if key not in scores:
                    scores[key] = [doc, 0.0]
                scores[key][1] += contribution

        _accumulate(dense_docs, config.DENSE_WEIGHT)
        _accumulate(sparse_docs, config.SPARSE_WEIGHT)

        return {key: (doc, score) for key, (doc, score) in scores.items()}

    @staticmethod
    def _apply_recency_weighting(fused: dict) -> List[Tuple[Document, float]]:
        """Blend each fused RRF score with a recency decay factor. See config.py for knobs."""
        now = datetime.now(timezone.utc)
        reweighted = []

        for doc, rrf_score in fused.values():
            doc_date_str = doc.metadata.get("doc_date")
            recency_factor = 1.0
            if doc_date_str:
                doc_date = datetime.fromisoformat(doc_date_str)
                age_days = max((now - doc_date).days, 0)
                raw_decay = 0.5 ** (age_days / config.RECENCY_HALF_LIFE_DAYS)
                recency_factor = max(config.RECENCY_FLOOR, raw_decay)

            blended = rrf_score * ((1 - config.RECENCY_WEIGHT) + config.RECENCY_WEIGHT * recency_factor)
            reweighted.append((doc, blended))

        return reweighted

    def _rerank(
        self, query: str, scored_docs: List[Tuple[Document, float]]
    ) -> List[Tuple[Document, float]]:
        """Cross-encoder reranking: one calibrated relevance score per (query, doc) pair."""
        if not scored_docs:
            return scored_docs
        documents = [doc for doc, _score in scored_docs]
        pairs = [(query, doc.page_content) for doc in documents]
        ce_scores = self._cross_encoder.score(pairs)
        return sorted(zip(documents, ce_scores), key=lambda pair: pair[1], reverse=True)

    @staticmethod
    def _to_retrieved_passage(doc: Document, score: float) -> RetrievedPassage:
        metadata = doc.metadata
        section = metadata.get("section", "Unknown section")
        page = metadata.get("page")
        section_reference = f"{section} (p.{page})" if page else section

        return RetrievedPassage(
            passage_id=str(uuid.uuid4()),
            text=doc.page_content,
            source_document=metadata.get("doc_name", "unknown_document"),
            section_reference=section_reference,
            similarity_score=round(float(score), 4),
            retrieved_at=datetime.now(timezone.utc),
        )


def _document_key(doc: Document) -> str:
    """Stable identity for a chunk across the dense and sparse result lists."""
    return f"{doc.metadata.get('doc_name')}::{doc.metadata.get('page')}::{hash(doc.page_content)}"


# Module-level singleton, mirroring core/graph.py's get_compiled_graph() pattern

_store: Optional[FinAgentVectorStore] = None


def get_vector_store() -> FinAgentVectorStore:
    """Lazily build+cache the vector store, loading a persisted index if one exists."""
    global _store
    if _store is None:
        _store = FinAgentVectorStore()
        _store.load()  # no-op if nothing has been persisted yet
    return _store