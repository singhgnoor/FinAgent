"""
Retrieval Agent (2.2): Accept a natural-language query (built from the
normalized event), search the RAG vector store, and return top-k passages
with source attribution. Falls back to generated financial context when
the vector store is empty.
"""

import uuid
import time
import re
from datetime import datetime, timezone
from typing import List, Optional

from core.state import (
    AgentName,
    FinAgentState,
    NormalizedEvent,
    RetrievedPassage,
    SignalType,
    new_trace_event,
    RAGQuery,
)

from config import TOP_K_DEFAULT, ASSET_ALIASES
from rag.vector_store import get_vector_store
from core.log import get_logger

logger = get_logger(__name__)


# Query builder helper

def _normalize_asset_token(asset: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", "", asset.upper()).strip()


def _resolve_aliases(asset: str) -> List[str]:
    """Alias list for an asset. Falls back to a fuzzy substring match against
    known keys, then to the raw token itself if nothing matches — so an
    unmapped ticker degrades to 'filter on exactly this string' rather than
    silently filtering on nothing."""
    token = _normalize_asset_token(asset)
    if not token:
        return []
    if token in ASSET_ALIASES:
        return ASSET_ALIASES[token]
    for key, aliases in ASSET_ALIASES.items():
        if token in key or key in token:
            return aliases
    return [token]


def _build_query(state: FinAgentState) -> Optional[RAGQuery]:
    event = state.get("normalized_event")
    if event is None:
        return None

    asset = event.asset or ""
    aliases = _resolve_aliases(asset) if asset else []

    if event.event_type == SignalType.PRICE_TICK and event.price_data:
        pd = event.price_data
        rsi_desc = (
            "overbought" if pd.rsi and pd.rsi > 70
            else "oversold" if pd.rsi and pd.rsi < 30
            else "neutral RSI"
        )
        trend_desc = "above" if pd.close > (pd.moving_average or 0) else "below"

        # Semantic leg: concepts, not just numbers — this is what dense
        # embeddings actually key off of.
        semantic_query = (
            f"{asset} financial performance, valuation, and business outlook. "
            f"Current technical context: price is {trend_desc} its moving average, "
            f"showing {rsi_desc} momentum, on volume of {pd.volume:.0f}. "
            f"Relevant considerations: growth drivers, risk factors, sector "
            f"positioning, and how comparable price action has historically resolved."
        )

        # Keyword leg: dense in exact tokens BM25 rewards — ticker, aliases,
        # literal indicator names and values. No filler.
        keyword_query = (
            f"{asset} {' '.join(aliases)} RSI {pd.rsi:.1f} "
            f"moving average {pd.moving_average:.2f} close {pd.close} "
            f"volume {pd.volume:.0f} {rsi_desc} {trend_desc} moving average"
        )
    else:
        base_text = event.normalized_text or ""
        # Prefix asset context explicitly — a short headline like "cuts
        # guidance for Q3" carries no company signal on its own, and that's
        # exactly the case where FAISS/BM25 have historically been picking
        # up the wrong company's chunks.
        semantic_query = (
            f"{asset}: {base_text}. Assess materiality to future cash flows, "
            f"whether this is already priced in, and how it compares to the "
            f"company's recent fundamental trajectory."
        )
        keyword_query = f"{asset} {' '.join(aliases)} {base_text}".strip()

    return RAGQuery(
        semantic_query=semantic_query.strip(),
        keyword_query=keyword_query.strip(),
        asset=asset or None,
        asset_aliases=aliases,
    )

def _vector_search(rag_query: RAGQuery, top_k: int = TOP_K_DEFAULT) -> List[RetrievedPassage]:
    """Real hybrid RAG search via rag/vector_store.py."""
    store = get_vector_store()
    return store.retrieve(rag_query, top_k=top_k)

def _fallback_passages(event: NormalizedEvent) -> List[RetrievedPassage]:
    """Generate financial context passages when the vector store is empty."""
    now = datetime.now(timezone.utc)
    asset = event.asset or "the asset"

    if event.event_type == SignalType.PRICE_TICK and event.price_data:
        pd = event.price_data
        rsi_note = "overbought territory" if pd.rsi and pd.rsi > 70 else "oversold territory" if pd.rsi and pd.rsi < 30 else "neutral territory"
        ma_note = "above" if pd.close > (pd.moving_average or 0) else "below"

        return [
            RetrievedPassage(
                passage_id=str(uuid.uuid4()),
                text=f"Technical analysis of {asset}: Price at {pd.close} with volume of {pd.volume:.0f}. "
                     f"The RSI(14) of {pd.rsi:.1f} suggests {rsi_note}. Price is trading {ma_note} the 20-period SMA "
                     f"of {pd.moving_average:.2f}. Daily range: {pd.low} - {pd.high} on open of {pd.open}. "
                     f"Traders often interpret high volume breakouts above resistance as confirmation of momentum, "
                     f"while low volume moves above moving averages may indicate weak follow-through.",
                source_document="technical_analysis_framework",
                section_reference="Price Action & Momentum Indicators",
                similarity_score=0.75,
                retrieved_at=now,
                source_type="fallback_generic",
                grounded=False,
                metadata={"kind": "generated_fallback", "asset": asset, "framework": "technical_analysis"},
            ),
            RetrievedPassage(
                passage_id=str(uuid.uuid4()),
                text=f"Market context for {asset}: Financial markets price assets based on discounted future cash flows. "
                     f"Short-term price movements are driven by order flow, sentiment, and positioning rather than fundamentals. "
                     f"A single price bar provides limited signal; confirmation from volume, follow-through in subsequent "
                     f"sessions, and alignment with broader market structure increases reliability of any directional view.",
                source_document="market_microstructure_primer",
                section_reference="Signal Reliability & Confirmation",
                similarity_score=0.65,
                retrieved_at=now,
                source_type="fallback_generic",
                grounded=False,
                metadata={"kind": "generated_fallback", "asset": asset, "framework": "market_microstructure"},
            ),
            RetrievedPassage(
                passage_id=str(uuid.uuid4()),
                text=f"Risk management guideline for {asset}: Position sizing should account for the current price's distance "
                     f"from key support/resistance levels. When RSI is in neutral range (30-70), directional bias carries "
                     f"moderate conviction. Traders typically set stops below the recent swing low for long positions. "
                     f"Volume analysis helps distinguish genuine breakouts from noise.",
                source_document="risk_management_framework",
                section_reference="Position Sizing & Stop Placement",
                similarity_score=0.60,
                retrieved_at=now,
                source_type="fallback_generic",
                grounded=False,
                metadata={"kind": "generated_fallback", "asset": asset, "framework": "risk_management"},
            ),
        ]

    return [
        RetrievedPassage(
            passage_id=str(uuid.uuid4()),
            text=f"Fundamental context for {asset}: Companies and assets trade based on their earnings power, "
                 f"competitive position, industry trends, and macroeconomic environment. News events should be evaluated "
                 f"for their materiality to future cash flows and whether the market has already priced in the information. "
                 f"High-impact news on liquid assets tends to be incorporated rapidly into price.",
            source_document="fundamental_analysis_framework",
            section_reference="Event Materiality Assessment",
            similarity_score=0.70,
            retrieved_at=now,
            source_type="fallback_generic",
            grounded=False,
            metadata={"kind": "generated_fallback", "asset": asset, "framework": "fundamental_analysis"},
        ),
        RetrievedPassage(
            passage_id=str(uuid.uuid4()),
            text=f"Sentiment analysis context for {asset}: Market sentiment around news events can be gauged by "
                 f"the initial price reaction, volume profile, and subsequent follow-through. A news-driven move on "
                 f"above-average volume with minimal retracement suggests conviction, while low-volume moves or quick "
                 f"reversals indicate skepticism. Sentiment is most reliable when multiple independent signals converge.",
            source_document="sentiment_analysis_guide",
            section_reference="News-Driven Price Action",
            similarity_score=0.60,
            retrieved_at=now,
            source_type="fallback_generic",
            grounded=False,
            metadata={"kind": "generated_fallback", "asset": asset, "framework": "sentiment_analysis"},
        ),
    ]


def retrieval_node(state: FinAgentState) -> dict:
    """LangGraph node entrypoint. Builds a query, retrieves passages, falls back to generated context."""
    node_start = time.perf_counter()
    query = _build_query(state)

    logger.info("[retrieval] Node entry: building RAG query")

    if not query:
        elapsed = time.perf_counter() - node_start
        trace = new_trace_event(
            agent=AgentName.RETRIEVAL,
            action="skip_no_query",
            output_summary="no-op, no normalized_event in state",
            duration_ms=round(elapsed * 1000, 2),
            status="fallback",
        )
        logger.debug(f"[retrieval] Trace event: {trace.model_dump_json()}")
        return {"trace_log": [trace]}

    logger.debug(f"[retrieval] Query: {query}...")

    retrieval_error = None
    try:
        passages = _vector_search(query)
        logger.info(f"[retrieval] Vector search returned {len(passages)} passages")
    except Exception as e:
        logger.exception(f"[retrieval] Vector search failed: {type(e).__name__}: {str(e)}")
        retrieval_error = str(e)
        passages = []

    grounded = bool(passages) and all(p.grounded and p.source_type == "kb_retrieved" for p in passages)
    if not passages:
        event = state.get("normalized_event")
        if event:
            logger.info("[retrieval] Vector store empty — using generated financial context passages")
            passages = _fallback_passages(event)
        else:
            logger.warning("[retrieval] No passages retrieved and no event for fallback")

    elapsed = time.perf_counter() - node_start

    trace = new_trace_event(
        agent=AgentName.RETRIEVAL,
        action="similarity_search",
        tool_calls=["vector_store.retrieve"],
        input_summary=query.__str__(),
        output_summary=(f"{len(passages)} KB-grounded passages retrieved" if grounded
                        else f"{len(passages)} fallback (non-KB) passages"),
        duration_ms=round(elapsed * 1000, 2),
        status="ok" if grounded else "fallback",
        error_message=None if grounded else (retrieval_error or "Knowledge base returned no matching passages"),
    )

    logger.info(
        f"[retrieval] Node exit: {len(passages)} passages, elapsed={elapsed:.3f}s"
    )
    logger.debug(f"[retrieval] Trace event: {trace.model_dump_json()}")

    return {
        "rag_query": query,
        "retrieved_passages": passages,
        "retrieval_grounded": grounded,
        "trace_log": [trace],
        **({"errors": [f"retrieval_agent: {retrieval_error or 'knowledge base returned no matching passages'}"]} if not grounded else {}),
    }
