"""
Ingestion Agent (2.1) — Real-Time Signal Ingestion & Preprocessing

Role: Parse, timestamp, and normalise all incoming signals (numerical price ticks,
unstructured news text, semi-structured documents) into a unified internal representation
(NormalizedEvent). For numerical price ticks, it statefully tracks the price history window
and dynamically calculates indicators like the 20-period Moving Average (SMA) and
14-period RSI.
"""

import json
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, List, Any

import config
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
from core.log import get_logger

logger = get_logger(__name__)

PRICE_HISTORY_FILE = config.DATA_DIR / "price_history.json"


def _load_price_history() -> Dict[str, List[float]]:
    """Load price history cache from disk."""
    if not os.path.exists(PRICE_HISTORY_FILE):
        return {}
    try:
        with open(PRICE_HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_price_history(history: Dict[str, List[float]]):
    """Save price history cache to disk."""
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(PRICE_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception:
        pass


def _calculate_sma(prices: List[float], period: int = 20) -> float:
    """Calculate simple moving average over the specified period window."""
    if not prices:
        return 0.0
    actual_period = min(period, len(prices))
    return sum(prices[-actual_period:]) / actual_period


def _calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate RSI using simple average gain/loss over the period window.
    Defaults to 50.0 (neutral) when price changes are flat or history is insufficient.
    """
    if len(prices) < 2:
        return 50.0

    gains = []
    losses = []
    for i in range(len(prices) - 1):
        diff = prices[i+1] - prices[i]
        if diff > 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)

    actual_period = min(period, len(gains))
    if actual_period == 0:
        return 50.0

    avg_gain = sum(gains[-actual_period:]) / actual_period
    avg_loss = sum(losses[-actual_period:]) / actual_period

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _extract_ticker_from_text(text: str) -> str:
    """Heuristic helper to search unstructured news/filings for known tickers."""
    upper_text = text.upper()
    ticker_map = {
        "RELIANCE": "RELIANCE",
        "JIO": "RELIANCE",
        "TCS": "TCS",
        "TATA CONSULTANCY": "TCS",
        "INFY": "INFY",
        "INFOSYS": "INFY",
        "WIPRO": "WIPRO",
        "HDFC": "HDFC",
        "ICICI": "ICICI",
    }
    for keyword, ticker in ticker_map.items():
        if keyword in upper_text:
            return ticker
    return "GENERAL"


def _normalize_raw_signal(raw: RawSignal) -> NormalizedEvent:
    """Turn a RawSignal into a unified NormalizedEvent with calculated metrics."""
    now = datetime.now(timezone.utc)
    asset = raw.payload.get("asset", "").strip() or None

    price_data = text_data = document_data = None
    normalized_text = ""

    if raw.signal_type == SignalType.PRICE_TICK:
        # Resolve target asset name (default to general sector/unknown if missing)
        resolved_asset = asset or "UNKNOWN"
        close_val = float(raw.payload.get("close", 0.0))

        # Update sliding price history window
        history = _load_price_history()
        ticker_history = history.get(resolved_asset, [])
        ticker_history.append(close_val)
        ticker_history = ticker_history[-100:]  # cap window history size
        history[resolved_asset] = ticker_history
        _save_price_history(history)

        # Compute dynamic metrics
        rsi_val = _calculate_rsi(ticker_history, period=14)
        ma_val = _calculate_sma(ticker_history, period=20)

        price_data = PriceData(
            open=float(raw.payload.get("open", 0.0)),
            high=float(raw.payload.get("high", 0.0)),
            low=float(raw.payload.get("low", 0.0)),
            close=close_val,
            volume=float(raw.payload.get("volume", 0.0)),
            moving_average=ma_val,
            rsi=rsi_val,
        )
        asset = resolved_asset
        normalized_text = (
            f"TICK for {asset}: close={price_data.close}, volume={price_data.volume}, "
            f"MA(20)={price_data.moving_average:.2f}, RSI(14)={price_data.rsi:.2f}"
        )

    elif raw.signal_type == SignalType.NEWS_TEXT:
        headline = raw.payload.get("headline", "")
        summary = raw.payload.get("summary")
        full_text = raw.payload.get("full_text")

        text_data = TextData(
            headline=headline,
            summary=summary,
            full_text=full_text,
        )
        
        # If no asset is declared, infer it from text
        if not asset:
            combined_search = " ".join([headline, summary or "", full_text or ""])
            asset = _extract_ticker_from_text(combined_search)

        normalized_text = f"NEWS [{asset}]: {headline}"

    elif raw.signal_type == SignalType.DOCUMENT:
        document_data = DocumentData(
            doc_name=raw.payload.get("doc_name", "unknown_document"),
            doc_type=raw.payload.get("doc_type", "filing"),
            page_or_section=raw.payload.get("page_or_section"),
            excerpt=raw.payload.get("excerpt", ""),
        )
        
        if not asset:
            combined_search = f"{document_data.doc_name} {document_data.excerpt}"
            asset = _extract_ticker_from_text(combined_search)

        normalized_text = f"DOCUMENT [{asset} - {document_data.doc_name}]: {document_data.excerpt}"

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
    node_start = time.perf_counter()
    raw_signal = state.get("raw_signal")

    logger.info("[ingestion] Node entry: raw_signal present" if raw_signal else "[ingestion] Node entry: NO raw_signal")

    if raw_signal is None:
        logger.warning("[ingestion] Skipping: no raw_signal in state")
        trace = new_trace_event(
            agent=AgentName.INGESTION,
            action="skip_no_raw_signal",
            output_summary="no-op, no raw_signal in state",
            status="fallback",
        )
        logger.debug(f"[ingestion] Trace event: {trace.model_dump_json()}")
        return {"trace_log": [trace]}

    normalized_event = _normalize_raw_signal(raw_signal)
    logger.debug(f"[ingestion] Normalized raw_signal (type={raw_signal.signal_type.value}) -> event_id={normalized_event.event_id}")

    elapsed = time.perf_counter() - node_start

    trace = new_trace_event(
        agent=AgentName.INGESTION,
        action="normalize_signal",
        input_summary=f"raw_signal type={raw_signal.signal_type.value}",
        output_summary=(
            f"normalized_event id={normalized_event.event_id}, "
            f"asset={normalized_event.asset or 'None'}, text={normalized_event.normalized_text[:50]}"
        ),
        duration_ms=round(elapsed * 1000, 2),
    )
    
    logger.info(
        f"[ingestion] Node exit: normalized_event_id={normalized_event.event_id}, "
        f"asset={normalized_event.asset}, elapsed={elapsed:.3f}s"
    )
    logger.debug(f"[ingestion] Trace event: {trace.model_dump_json()}")

    return {
        "normalized_event": normalized_event,
        "trace_log": [trace],
    }