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
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

import config
from core.state import RetrievedPassage
from core.log import get_logger

logger = get_logger(__name__)

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
        logger.info(
            f"[vector_store] Initializing FinAgentVectorStore: "
            f"embedding_model={config.EMBEDDING_MODEL_NAME}, device={config.EMBEDDING_DEVICE}"
        )
        self._embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": config.EMBEDDING_DEVICE},
        )
        self._faiss_store: Optional[FAISS] = None
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._documents: List[Document] = []

        self._cross_encoder = None
        if config.ENABLE_RERANKING and _CROSS_ENCODER_AVAILABLE:
            logger.info(f"[vector_store] Initializing cross-encoder: {config.RERANK_MODEL_NAME}")
            self._cross_encoder = HuggingFaceCrossEncoder(model_name=config.RERANK_MODEL_NAME)
        elif config.ENABLE_RERANKING:
            logger.warning("[vector_store] Reranking enabled but cross-encoder unavailable")
        else:
            logger.debug("[vector_store] Cross-encoder reranking disabled")

    @property
    def is_empty(self) -> bool:
        return self._faiss_store is None

    # -- ingestion -----------------------------------------------------

    def add_documents(self, documents: List[Document]) -> int:
        """Embed and index a batch of chunks (from rag/ingest.py). Returns chunks added."""
        if not documents:
            logger.debug("[vector_store] add_documents called with empty list")
            return 0

        logger.info(f"[vector_store] Adding {len(documents)} documents to index")
        if self._faiss_store is None:
            logger.debug("[vector_store] Creating new FAISS index")
            self._faiss_store = FAISS.from_documents(documents, self._embeddings)
        else:
            logger.debug("[vector_store] Appending to existing FAISS index")
            self._faiss_store.add_documents(documents)

        self._documents.extend(documents)
        # BM25 has no incremental add in LangChain, so rebuild from the full
        # corpus. Fine at knowledge-base-ingestion cadence (uploads), not
        # meant for a high-frequency-write workload.
        logger.debug(f"[vector_store] Rebuilding BM25 index over {len(self._documents)} total documents")
        self._bm25_retriever = BM25Retriever.from_documents(self._documents)
        self._bm25_retriever.k = config.SPARSE_TOP_K

        logger.info(f"[vector_store] Index updated: FAISS+BM25, total docs={len(self._documents)}")
        return len(documents)

    # -- persistence -----------------------------------------------------

    def save(self, path: str = config.VECTOR_STORE_DIR) -> None:
        if self._faiss_store is None:
            logger.error("[vector_store] Cannot save: no documents have been indexed yet")
            raise ValueError("Nothing to save — no documents have been indexed yet.")
        logger.info(f"[vector_store] Saving vector store to {path}")
        os.makedirs(path, exist_ok=True)
        self._faiss_store.save_local(path)
        with open(os.path.join(path, "documents.pkl"), "wb") as f:
            pickle.dump(self._documents, f)
        logger.info(f"[vector_store] Vector store saved: {len(self._documents)} documents, {len(self._faiss_store.index_to_docstore_id)} FAISS index entries")

    def load(self, path: str = config.VECTOR_STORE_DIR) -> bool:
        """Returns True if an existing index was found on disk and loaded."""
        index_file = os.path.join(path, "index.faiss")
        docs_file = os.path.join(path, "documents.pkl")
        
        if not (os.path.exists(index_file) and os.path.exists(docs_file)):
            logger.debug(f"[vector_store] No persisted index found at {path} (expected files: index.faiss, documents.pkl)")
            return False

        logger.info(f"[vector_store] Loading persisted vector store from {path}")
        # allow_dangerous_deserialization: safe here because this only ever
        # loads an index this same app previously saved, never a third-party file.
        self._faiss_store = FAISS.load_local(
            path, self._embeddings, allow_dangerous_deserialization=True
        )
        with open(docs_file, "rb") as f:
            self._documents = pickle.load(f)
        self._bm25_retriever = BM25Retriever.from_documents(self._documents)
        self._bm25_retriever.k = config.SPARSE_TOP_K
        
        logger.info(f"[vector_store] Loaded: {len(self._documents)} documents in FAISS+BM25 indices")
        return True

    # -- retrieval -----------------------------------------------------

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievedPassage]:
        """
        Hybrid dense+sparse retrieval, fused with RRF, reweighted by
        recency, optionally reranked, and returned as RetrievedPassage
        objects ready to drop into FinAgentState.
        """
        retrieval_start = time.perf_counter()
        top_k = top_k or config.FINAL_TOP_K
        
        logger.info(f"[vector_store.retrieve] Query: {query[:100]}..." if len(query) > 100 else f"[vector_store.retrieve] Query: {query}")

        if self._faiss_store is None or self._bm25_retriever is None:
            logger.warning("[vector_store.retrieve] Index is empty (not initialized)")
            return []

        logger.debug("[vector_store.retrieve] Running dense (FAISS) retrieval...")
        dense_docs = self._faiss_store.similarity_search(query, k=config.DENSE_TOP_K)
        logger.info(f"[vector_store.retrieve] FAISS returned {len(dense_docs)} candidates (k={config.DENSE_TOP_K})")
        
        logger.debug("[vector_store.retrieve] Running sparse (BM25) retrieval...")
        sparse_docs = self._bm25_retriever.invoke(query)
        logger.info(f"[vector_store.retrieve] BM25 returned {len(sparse_docs)} candidates (k={config.SPARSE_TOP_K})")

        fused = self._reciprocal_rank_fusion(dense_docs, sparse_docs)
        logger.info(f"[vector_store.retrieve] RRF fused {len(fused)} unique documents from dense+sparse results")
        
        scored = self._apply_recency_weighting(fused)
        scored.sort(key=lambda pair: pair[1], reverse=True)
        logger.debug(f"[vector_store.retrieve] After recency weighting and sorting: {len(scored)} candidates")

        pool_size = config.RERANK_CANDIDATE_POOL if self._cross_encoder else top_k
        candidate_pool = scored[:pool_size]
        logger.debug(f"[vector_store.retrieve] Candidate pool size: {len(candidate_pool)} (will rerank={self._cross_encoder is not None})")

        if self._cross_encoder:
            logger.debug(f"[vector_store.retrieve] Running cross-encoder reranking on {len(candidate_pool)} candidates...")
            candidate_pool = self._rerank(query, candidate_pool)
        else:
            # Normalize raw RRF scores to [0, 1] range based on theoretical max
            max_rrf = (config.DENSE_WEIGHT + config.SPARSE_WEIGHT) / (config.RRF_K + 1)
            candidate_pool = [(doc, min(score / max_rrf, 1.0)) for doc, score in candidate_pool]
            logger.info(f"[vector_store.retrieve] After normalization: {len(candidate_pool)} scored candidates")

        final = candidate_pool[:top_k]
        logger.info(f"[vector_store.retrieve] Final top-k: {len(final)} passages selected (requested k={top_k})")
        
        retrieved_passages = [self._to_retrieved_passage(doc, score) for doc, score in final]
        
        for i, p in enumerate(retrieved_passages[:5]):
            logger.debug(
                f"[vector_store.retrieve] Final result {i+1}: id={p.passage_id}, score={p.similarity_score:.4f}, "
                f"source={p.source_document}, text_preview={p.text[:80]}..."
            )
        
        elapsed = time.perf_counter() - retrieval_start
        logger.info(f"[vector_store.retrieve] Retrieval completed in {elapsed:.3f}s: {len(retrieved_passages)} final passages")
        
        return retrieved_passages

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
        
        # Normalize raw logits using a sigmoid function to bound them in [0, 1]
        import math
        normalized_scores = [1.0 / (1.0 + math.exp(-float(s))) for s in ce_scores]
        
        return sorted(zip(documents, normalized_scores), key=lambda pair: pair[1], reverse=True)

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
        logger.info("[vector_store] Initializing module-level vector store singleton")
        _store = FinAgentVectorStore()
        loaded = _store.load()  # no-op if nothing has been persisted yet
        if not loaded:
            logger.info("[vector_store] No persisted index found; vector store ready for new ingestion")
        else:
            logger.info("[vector_store] Vector store loaded from persistence")
    return _store