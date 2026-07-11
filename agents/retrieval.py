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


def _build_query(state: FinAgentState) -> str:
    event = state.get("normalized_event")
    if event is None:
        return ""
    return f"Relevant context for: {event.normalized_text}"


def _fake_similarity_search(query: str, top_k: int = TOP_K_DEFAULT) -> List[RetrievedPassage]:
    """STUB: pretend vector search. Replace with rag/vector_store.py call."""
    now = datetime.now(timezone.utc)
    return [
        RetrievedPassage(
            passage_id=str(uuid.uuid4()),
            text=f"[stub passage {i + 1}] Sample retrieved context for query: '{query}'",
            source_document="sample_document.pdf",
            section_reference=f"p.{i + 1}",
            similarity_score=round(0.9 - i * 0.1, 2),
            retrieved_at=now,
        )
        for i in range(top_k)
    ]


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

    passages = _fake_similarity_search(query)

    trace = new_trace_event(
        agent=AgentName.RETRIEVAL,
        action="similarity_search",
        tool_calls=["vector_store.similarity_search (stub)"],
        input_summary=query,
        output_summary=f"{len(passages)} passages retrieved",
    )

    return {
        "rag_query": query,
        "retrieved_passages": passages,
        "trace_log": [trace],
    }