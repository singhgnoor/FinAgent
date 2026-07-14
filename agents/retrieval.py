"""
Retrieval Agent — Stub

Role (2.2): Accept a natural-language query (built from the normalized
event), search the RAG vector store, and return top-k passages with
source attribution.

STUB: returns hardcoded fake passages instead of calling a real vector
store. Swap `_fake_similarity_search` for a call into rag/vector_store.py
once that's built.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import List

from core.state import (
    AgentName,
    FinAgentState,
    RetrievedPassage,
    new_trace_event,
)

from config import TOP_K_DEFAULT
from rag.vector_store import get_vector_store
from core.log import get_logger

logger = get_logger(__name__)


def _build_query(state: FinAgentState) -> str:
    event = state.get("normalized_event")
    if event is None:
        return ""
    return f"Relevant context for: {event.normalized_text}"


def _vector_search(query: str, top_k: int = TOP_K_DEFAULT) -> List[RetrievedPassage]:
    """Real hybrid RAG search via rag/vector_store.py."""
    store = get_vector_store()
    return store.retrieve(query, top_k=top_k)


def retrieval_node(state: FinAgentState) -> dict:
    """LangGraph node entrypoint. Builds a query, retrieves passages."""
    node_start = time.perf_counter()
    query = _build_query(state)

    logger.info("[retrieval] Node entry: building RAG query")

    if not query:
        logger.warning("[retrieval] Skipping: no query produced (no normalized_event)")
        trace = new_trace_event(
            agent=AgentName.RETRIEVAL,
            action="skip_no_query",
            output_summary="no-op, no normalized_event in state",
            status="fallback",
        )
        logger.debug(f"[retrieval] Trace event: {trace.model_dump_json()}")
        return {"trace_log": [trace]}

    logger.debug(f"[retrieval] Query: {query[:150]}..." if len(query) > 150 else f"[retrieval] Query: {query}")

    try:
        passages = _vector_search(query)
        logger.info(f"[retrieval] Vector search returned {len(passages)} passages")
        
        if passages:
            for i, p in enumerate(passages[:5]):
                logger.debug(f"[retrieval] Passage {i+1}: id={p.passage_id}, score={p.similarity_score:.4f}, "
                           f"source={p.source_document}, text_preview={p.text[:100]}...")
        else:
            logger.warning("[retrieval] No passages retrieved (zero results)")
            
    except Exception as e:
        logger.exception(f"[retrieval] Vector search failed: {type(e).__name__}: {str(e)}")
        trace = new_trace_event(
            agent=AgentName.RETRIEVAL,
            action="similarity_search",
            tool_calls=["vector_store.retrieve"],
            input_summary=query,
            output_summary="retrieval failed",
            status="error",
            error_message=str(e),
        )
        logger.debug(f"[retrieval] Trace event (error): {trace.model_dump_json()}")
        return {"trace_log": [trace], "errors": [f"retrieval_agent: {e}"]}

    trace = new_trace_event(
        agent=AgentName.RETRIEVAL,
        action="similarity_search",
        tool_calls=["vector_store.retrieve"],
        input_summary=query,
        output_summary=f"{len(passages)} passages retrieved",
        status="ok" if passages else "fallback",
    )
    
    elapsed = time.perf_counter() - node_start
    logger.info(
        f"[retrieval] Node exit: {len(passages)} passages, elapsed={elapsed:.3f}s"
    )
    logger.debug(f"[retrieval] Trace event: {trace.model_dump_json()}")

    return {
        "rag_query": query,
        "retrieved_passages": passages,
        "trace_log": [trace],
    }