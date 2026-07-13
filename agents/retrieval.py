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
    query = _build_query(state)

    if not query:
        trace = new_trace_event(
            agent=AgentName.RETRIEVAL,
            action="skip_no_query",
            output_summary="no-op, no normalized_event in state",
            status="fallback",
        )
        return {"trace_log": [trace]}

    try:
        passages = _vector_search(query)
    except Exception as e:
        trace = new_trace_event(
            agent=AgentName.RETRIEVAL,
            action="similarity_search",
            tool_calls=["vector_store.retrieve"],
            input_summary=query,
            output_summary="retrieval failed",
            status="error",
            error_message=str(e),
        )
        return {"trace_log": [trace], "errors": [f"retrieval_agent: {e}"]}

    trace = new_trace_event(
        agent=AgentName.RETRIEVAL,
        action="similarity_search",
        tool_calls=["vector_store.retrieve"],
        input_summary=query,
        output_summary=f"{len(passages)} passages retrieved",
        status="ok" if passages else "fallback",
    )

    return {
        "rag_query": query,
        "retrieved_passages": passages,
        "trace_log": [trace],
    }