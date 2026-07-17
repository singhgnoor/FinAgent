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

SCORE TRANSPARENCY (see ScoreBundle below): every candidate carries five
separate score fields end to end — dense (cosine sim), sparse (raw BM25),
RRF-blended, recency-weighted, and reranker (raw logit + sigmoid
confidence). None of these is ever read as if it were another; that
conflation was the root cause of a prior debugging session's confusion
(scores appearing outside [0,1]) — compounded by FAISS previously
returning raw L2 distance mislabeled as similarity. See _resolve_distance_strategy().

Uses LangChain components throughout (FAISS, BM25Retriever, HuggingFace
embeddings, HuggingFace cross-encoder) per the "LangChain for agent
tooling" requirement, rather than hand-rolled retrieval clients.
"""
import os
import math
import pickle
import uuid
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores.utils import DistanceStrategy
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


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid. Converts an unbounded cross-encoder logit
    into a [0,1] confidence — the reranker's raw .score() output is NOT a
    probability, it's an unnormalized logit, so this must run before anything
    downstream treats it as a confidence value."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _resolve_distance_strategy() -> DistanceStrategy:
    mapping = {"cosine": DistanceStrategy.COSINE, "l2": DistanceStrategy.EUCLIDEAN_DISTANCE}
    key = getattr(config, "FAISS_DISTANCE_STRATEGY", "l2").lower()
    if key not in mapping:
        raise ValueError(
            f"Unknown FAISS_DISTANCE_STRATEGY={key!r} in config.py; expected one of {list(mapping)}"
        )
    return mapping[key]


@dataclass
class ScoreBundle:
    """Every score a candidate accumulates on its way through the pipeline,
    kept as separate fields on purpose — see the module docstring. `None`
    means that stage never touched this candidate (e.g. a BM25-only hit has
    no dense_score), which is itself useful debugging signal; don't coerce
    it to 0.0 upstream of logging.
    """
    dense_score: Optional[float] = None            # raw FAISS score. Cosine similarity in
                                                     # [-1,1] if config.FAISS_DISTANCE_STRATEGY
                                                     # == "cosine" (recommended); raw L2 distance
                                                     # (unbounded, lower=better) otherwise.
    sparse_score: Optional[float] = None            # raw BM25 score — unbounded, corpus-dependent,
                                                     # not comparable across queries.
    rrf_score: Optional[float] = None               # rank-position blend of the two above.
    recency_weighted_score: Optional[float] = None  # rrf_score reweighted by document age.
    rerank_logit: Optional[float] = None            # raw cross-encoder output — unbounded.
    rerank_confidence: Optional[float] = None        # sigmoid(rerank_logit) — this is the only
                                                       # field in this bundle that's a genuine
                                                       # [0,1] confidence.
    is_low_confidence: bool = False


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
        self._distance_strategy = _resolve_distance_strategy()
        normalize = getattr(config, "NORMALIZE_EMBEDDINGS", True)

        logger.info(
            f"[vector_store] distance_strategy={self._distance_strategy}, "
            f"normalize_embeddings={normalize} "
            f"(both must be consistent with whatever built the persisted index — "
            f"see config_changes.diff note about re-ingesting)"
        )
        self._embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": config.EMBEDDING_DEVICE},
            # Normalize ourselves rather than trusting FAISS's internal handling of the
            # distance strategy. On unit vectors, cosine similarity, dot product, and
            # L2 distance are all monotonically related — so this is a belt-and-suspenders
            # guarantee that dense_score is a genuine-bounded cosine similarity, not
            # whatever the index type happens to compute.
            encode_kwargs={"normalize_embeddings": normalize},
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
            logger.debug(f"[vector_store] Creating new FAISS index (distance_strategy={self._distance_strategy})")
            self._faiss_store = FAISS.from_documents(
                documents, self._embeddings, distance_strategy=self._distance_strategy
            )
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
        logger.info(
            f"[vector_store] Vector store saved: {len(self._documents)} documents, "
            f"{len(self._faiss_store.index_to_docstore_id)} FAISS index entries"
        )

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
            path,
            self._embeddings,
            allow_dangerous_deserialization=True,
            distance_strategy=self._distance_strategy,
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

        # dense_hits = self._faiss_store.similarity_search_with_score(query, k=config.DENSE_TOP_K)
        # Important change in function to get cosine scores (this is giving squared distance)
        dense_hits = self._faiss_store.similarity_search_with_relevance_scores(query, k=config.DENSE_TOP_K)
        # Writing score in cosine
        dense_hits = list(map(lambda t: (t[0], 1 - t[1] / 2), dense_hits))
        logger.info(
            f"[vector_store.retrieve] FAISS returned {len(dense_hits)} candidates "
            f"(k={config.DENSE_TOP_K}, distance_strategy={self._distance_strategy})"
        )

        sparse_hits = self._bm25_search_with_score(query, k=config.SPARSE_TOP_K)
        logger.info(f"[vector_store.retrieve] BM25 returned {len(sparse_hits)} candidates (k={config.SPARSE_TOP_K})")

        fused = self._reciprocal_rank_fusion(dense_hits, sparse_hits)
        logger.info(f"[vector_store.retrieve] RRF fused {len(fused)} unique documents from dense+sparse results")
        self._log_candidates("post-RRF", list(fused.values()))

        reweighted = self._apply_recency_weighting(fused)
        reweighted.sort(key=lambda pair: pair[1].recency_weighted_score, reverse=True)
        self._log_candidates("post-recency (sorted)", reweighted)

        pool_size = config.RERANK_CANDIDATE_POOL if self._cross_encoder else top_k
        candidate_pool = reweighted[:pool_size]
        logger.debug(
            f"[vector_store.retrieve] Candidate pool size: {len(candidate_pool)} "
            f"(will rerank={self._cross_encoder is not None})"
        )

        if self._cross_encoder:
            logger.debug(f"[vector_store.retrieve] Running cross-encoder reranking on {len(candidate_pool)} candidates...")
            candidate_pool = self._rerank(query, candidate_pool)
            self._log_candidates("post-rerank (sorted)", candidate_pool)

        final = candidate_pool[:top_k]
        logger.info(f"[vector_store.retrieve] Final top-k: {len(final)} passages selected (requested k={top_k})")

        retrieved_passages = [self._to_retrieved_passage(doc, bundle) for doc, bundle in final]

        for i, p in enumerate(retrieved_passages[:5]):
            logger.debug(
                f"[vector_store.retrieve] Final result {i+1}: id={p.passage_id}, score={p.similarity_score:.4f}, "
                f"source={p.source_document}, text_preview={p.text[:80]}..."
            )

        elapsed = time.perf_counter() - retrieval_start
        logger.info(f"[vector_store.retrieve] Retrieval completed in {elapsed:.3f}s: {len(retrieved_passages)} final passages")

        return retrieved_passages

    # -- internal helpers ------------------------------------------------
    def _bm25_search_with_score(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """
        BM25Retriever.invoke() returns bare Documents — LangChain discards the
        score computed inside rank_bm25. Pull it straight from the underlying
        vectorizer instead of re-deriving it a second time.

        NOTE: this reaches into BM25Retriever's internal attributes
        (preprocess_func, vectorizer, docs), which are not a stable public
        API. If this breaks on your installed langchain_community version,
        paste me `dir(self._bm25_retriever)` and I'll fix this function —
        don't let me guess at attribute names for you.
        """
        if self._bm25_retriever is None:
            return []
        processed_query = self._bm25_retriever.preprocess_func(query)
        raw_scores = self._bm25_retriever.vectorizer.get_scores(processed_query)
        scored = list(zip(self._bm25_retriever.docs, raw_scores))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [(doc, float(score)) for doc, score in scored[:k]]

    @staticmethod
    def _reciprocal_rank_fusion(
        dense_hits: List[Tuple[Document, float]],
        sparse_hits: List[Tuple[Document, float]],
        rrf_k: int = None,
    ) -> dict:
        """
        Combines two ranked lists into one score per unique chunk using
        Reciprocal Rank Fusion: score(d) = sum(weight / (rrf_k + rank + 1))
        over every retriever d appeared in. Works on RANK POSITION, not raw
        score, which is what lets us combine cosine similarity and BM25's
        unbounded term-frequency score without calibrating either one.

        The raw dense/sparse scores are captured on the ScoreBundle purely
        for transparency/logging — they never feed into the RRF math itself.
        """
        rrf_k = rrf_k if rrf_k is not None else config.RRF_K
        bundles: dict = {}

        def _accumulate(hits: List[Tuple[Document, float]], weight: float, raw_score_field: str):
            for rank, (doc, raw_score) in enumerate(hits):
                key = _document_key(doc)
                if key not in bundles:
                    bundles[key] = [doc, ScoreBundle()]
                _, bundle = bundles[key]
                setattr(bundle, raw_score_field, float(raw_score))
                contribution = weight / (rrf_k + rank + 1)
                bundle.rrf_score = (bundle.rrf_score or 0.0) + contribution

        _accumulate(dense_hits, config.DENSE_WEIGHT, "dense_score")
        _accumulate(sparse_hits, config.SPARSE_WEIGHT, "sparse_score")
        return {key: (doc, bundle) for key, (doc, bundle) in bundles.items()}

    @staticmethod
    def _apply_recency_weighting(fused: dict) -> List[Tuple[Document, ScoreBundle]]:
        """Blend each fused RRF score with a recency decay factor. See config.py for knobs."""
        now = datetime.now(timezone.utc)
        reweighted = []
        for doc, bundle in fused.values():
            doc_date_str = doc.metadata.get("doc_date")
            recency_factor = 1.0
            if doc_date_str:
                doc_date = datetime.fromisoformat(doc_date_str)
                age_days = max((now - doc_date).days, 0)
                raw_decay = 0.5 ** (age_days / config.RECENCY_HALF_LIFE_DAYS)
                recency_factor = max(config.RECENCY_FLOOR, raw_decay)
            rrf_score = bundle.rrf_score or 0.0
            bundle.recency_weighted_score = rrf_score * (
                (1 - config.RECENCY_WEIGHT) + config.RECENCY_WEIGHT * recency_factor
            )
            reweighted.append((doc, bundle))
        return reweighted

    def _rerank(
        self, query: str, candidates: List[Tuple[Document, ScoreBundle]]
    ) -> List[Tuple[Document, ScoreBundle]]:
        """Cross-encoder reranking: one calibrated relevance score per (query, doc)
        pair. Applies sigmoid to the raw logit (goal #2/#3) and flags the top
        result low-confidence if it's below config.RERANK_CONFIDENCE_THRESHOLD."""
        if not candidates:
            return candidates
        documents = [doc for doc, _bundle in candidates]
        pairs = [(query, doc.page_content) for doc in documents]
        raw_logits = self._cross_encoder.score(pairs)

        for (doc, bundle), logit in zip(candidates, raw_logits):
            bundle.rerank_logit = float(logit)
            bundle.rerank_confidence = _sigmoid(float(logit))

        candidates.sort(key=lambda pair: pair[1].rerank_confidence, reverse=True)

        threshold = getattr(config, "RERANK_CONFIDENCE_THRESHOLD", 0.3)
        if candidates and candidates[0][1].rerank_confidence < threshold:
            candidates[0][1].is_low_confidence = True
            logger.warning(
                f"[vector_store._rerank] Top candidate confidence "
                f"{candidates[0][1].rerank_confidence:.4f} below threshold {threshold} — flagging low-confidence"
            )
        return candidates

    @staticmethod
    def _log_candidates(stage: str, candidates: List[Tuple[Document, ScoreBundle]], limit: int = 10) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        logger.debug(f"[vector_store] --- {stage}: top {min(limit, len(candidates))} of {len(candidates)} candidates ---")
        for i, (doc, bundle) in enumerate(candidates[:limit]):
            logger.debug(
                f"  #{i+1} {doc.metadata.get('doc_name', '?')} p.{doc.metadata.get('page', '?')} | "
                f"dense={bundle.dense_score} sparse={bundle.sparse_score} rrf={bundle.rrf_score} "
                f"recency={bundle.recency_weighted_score} rerank_logit={bundle.rerank_logit} "
                f"rerank_conf={bundle.rerank_confidence} low_conf={bundle.is_low_confidence}"
            )

    @staticmethod
    def _to_retrieved_passage(doc: Document, bundle: ScoreBundle) -> RetrievedPassage:
        metadata = doc.metadata
        section = metadata.get("section", "Unknown section")
        page = metadata.get("page")
        section_reference = f"{section} (p.{page})" if page else section

        # NOTE — this is a known stopgap: RetrievedPassage currently exposes only
        # one `similarity_score` slot, so this line necessarily collapses five
        # tracked scores into one number (sigmoid rerank confidence when reranking
        # ran, else the recency-weighted RRF score — never the two conflated with
        # each other, at least). All five components are still logged separately
        # above via _log_candidates, they just don't survive past this function
        # yet. Send me core/state.py's RetrievedPassage definition and I'll add
        # dense_score / sparse_score / rrf_score / recency_weighted_score /
        # rerank_logit / rerank_confidence / is_low_confidence as real fields
        # instead of guessing at a schema that might break the Decision Agent.
        final_score = bundle.rerank_confidence if bundle.rerank_confidence is not None else bundle.recency_weighted_score
        if bundle.is_low_confidence:
            section_reference = f"{section_reference} [LOW CONFIDENCE]"

        return RetrievedPassage(
            passage_id=str(uuid.uuid4()),
            text=doc.page_content,
            source_document=metadata.get("doc_name", "unknown_document"),
            section_reference=section_reference,
            similarity_score=round(float(final_score), 4),
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