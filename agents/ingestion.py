"""
Ingestion Agent — Stub

Role (2.1): Parse and normalize incoming market signals — price ticks,
news text, or documents — into a single unified NormalizedEvent, then
push it onto the shared graph state.

This is a STUB: it does the minimum needed to produce a valid
NormalizedEvent so the rest of the pipeline can be wired and tested.
`_normalize_raw_signal` is to be replaced with real parsing logic
(CSV/API replay, RSS parsing, PDF extraction) later.
"""

import uuid
from datetime import datetime, timezone

from core.state import (
    AgentName,
    DocumentData,
    FinAgentState,
    NormalizedEvent,
    PriceData,
    RawSignal,
    SignalType,
    TextData,
    new_trace_event,
)


def _normalize_raw_signal(raw: RawSignal) -> NormalizedEvent:
    """Turn a RawSignal into a unified NormalizedEvent. STUB LOGIC."""
    now = datetime.now(timezone.utc)
    asset = raw.payload.get("asset")

    price_data = text_data = document_data = None
    normalized_text = ""

    if raw.signal_type == SignalType.PRICE_TICK:
        price_data = PriceData(
            open=raw.payload.get("open", 0.0),
            high=raw.payload.get("high", 0.0),
            low=raw.payload.get("low", 0.0),
            close=raw.payload.get("close", 0.0),
            volume=raw.payload.get("volume", 0.0),
            moving_average=raw.payload.get("moving_average"),
            rsi=raw.payload.get("rsi"),
        )
        normalized_text = f"{asset} price tick: close={price_data.close}, volume={price_data.volume}"

    elif raw.signal_type == SignalType.NEWS_TEXT:
        text_data = TextData(
            headline=raw.payload.get("headline", ""),
            summary=raw.payload.get("summary"),
            full_text=raw.payload.get("full_text"),
        )
        normalized_text = text_data.headline

    elif raw.signal_type == SignalType.DOCUMENT:
        document_data = DocumentData(
            doc_name=raw.payload.get("doc_name", "unknown_document"),
            doc_type=raw.payload.get("doc_type", "filing"),
            page_or_section=raw.payload.get("page_or_section"),
            excerpt=raw.payload.get("excerpt", ""),
        )
        normalized_text = document_data.excerpt

    return NormalizedEvent(
        event_id=str(uuid.uuid4()),
        event_type=raw.signal_type,
        asset=asset,
        source=raw.source,
        timestamp=raw.received_at,
        ingested_at=now,
        normalized_text=normalized_text,
        price_data=price_data,
        text_data=text_data,
        document_data=document_data,
    )


def ingestion_node(state: FinAgentState) -> dict:
    """
    LangGraph node entrypoint. Reads `raw_signal` from state, produces
    `normalized_event`, and appends one trace event.
    """
    raw_signal = state.get("raw_signal")

    if raw_signal is None:
        trace = new_trace_event(
            agent=AgentName.INGESTION,
            action="skip_no_raw_signal",
            output_summary="no-op, no raw_signal in state",
            status="fallback",
        )
        return {"trace_log": [trace]}

    normalized_event = _normalize_raw_signal(raw_signal)

    trace = new_trace_event(
        agent=AgentName.INGESTION,
        action="normalize_signal",
        input_summary=f"raw_signal type={raw_signal.signal_type.value}",
        output_summary=f"normalized_event id={normalized_event.event_id}",
    )

    return {
        "normalized_event": normalized_event,
        "trace_log": [trace],
    }