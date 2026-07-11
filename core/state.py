"""
FinAgent — Shared LangGraph State

This file is the backbone of the whole system. Every agent reads from and
writes to this shared state object — no direct function calls between
agents are allowed, so this schema IS the inter-agent contract.

Design notes:
- Domain objects (RawSignal, NormalizedEvent, RetrievedPassage, Hypothesis,
  DecisionArtifact, TraceEvent) are Pydantic models: they give us validation
  and a clear, typed shape for each artifact the pipeline produces.
- FinAgentState is a TypedDict, which is what LangGraph expects for graph
  state. Single-value fields (e.g. `hypothesis`) get overwritten each time
  a node returns them. List fields that should ACCUMULATE across node
  calls (trace_log, errors) use Annotated[..., operator.add] so LangGraph
  merges them instead of replacing them.
- Every enum mirrors a closed set of values named explicitly in the
  problem statement (e.g. Action = BUY/SELL/HOLD/WATCH), so invalid values
  fail fast instead of silently drifting.
"""

from __future__ import annotations

import operator
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import Annotated, TypedDict


# Enums — closed vocabularies pulled straight from the problem statement

class SignalType(str, Enum):
    PRICE_TICK = "price_tick"       # structured numerical (OHLCV, indicators)
    NEWS_TEXT = "news_text"         # unstructured text (headlines, summaries)
    DOCUMENT = "document"           # semi-structured (earnings calls, filings)


class Classification(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TimeHorizon(str, Enum):
    INTRADAY = "intraday"
    SHORT_TERM = "short_term"       # 1-5 days
    MEDIUM_TERM = "medium_term"     # 1-4 weeks


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"                 # no action yet, monitor


class ConfidenceLevel(str, Enum):
    HIGH = "High"                   # > 70
    MEDIUM = "Medium"               # 40-70
    LOW = "Low"                     # < 40


class AgentName(str, Enum):
    INGESTION = "ingestion_agent"
    RETRIEVAL = "retrieval_agent"
    ANALYSIS = "analysis_agent"
    DECISION = "decision_agent"


def confidence_to_level(score: int) -> ConfidenceLevel:
    """Map a 0-100 confidence score to the High/Medium/Low bands from the spec."""
    if score > 70:
        return ConfidenceLevel.HIGH
    if score >= 40:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


# 2.1 Ingestion — raw input and its normalized form

class RawSignal(BaseModel):
    """Whatever comes off a data feed, before any parsing/normalisation."""
    raw_id: str
    signal_type: SignalType
    source: str                      # e.g. "yfinance", "rss_feed", "upload"
    payload: Dict[str, Any]          # untyped — shape depends on signal_type
    received_at: datetime


class PriceData(BaseModel):
    """Normalized structured numerical data (2.1, bullet 1)."""
    open: float
    high: float
    low: float
    close: float
    volume: float
    moving_average: Optional[float] = None
    rsi: Optional[float] = None


class TextData(BaseModel):
    """Normalized unstructured text — news headlines/summaries (2.1, bullet 2)."""
    headline: str
    summary: Optional[str] = None
    full_text: Optional[str] = None


class DocumentData(BaseModel):
    """Normalized semi-structured documents — transcripts/filings (2.1, bullet 3)."""
    doc_name: str
    doc_type: str                    # e.g. "earnings_call", "10-K", "filing"
    page_or_section: Optional[str] = None
    excerpt: str


class NormalizedEvent(BaseModel):
    """
    The unified internal representation every downstream agent consumes,
    regardless of which of the three input modalities it came from.
    """
    event_id: str
    event_type: SignalType
    asset: Optional[str] = None      # ticker/sector, when known
    source: str
    timestamp: datetime              # timestamp of the underlying event
    ingested_at: datetime            # when the pipeline processed it
    normalized_text: str             # unified text repr, used for RAG queries + LLM input
    price_data: Optional[PriceData] = None
    text_data: Optional[TextData] = None
    document_data: Optional[DocumentData] = None


# 2.2 RAG-Powered Context Retrieval

class RetrievedPassage(BaseModel):
    """A single retrieved chunk, grounded with source attribution."""
    passage_id: str
    text: str
    source_document: str
    section_reference: Optional[str] = None   # page or section number
    similarity_score: float
    retrieved_at: datetime


# 2.3 Signal Analysis & Hypothesis

class Hypothesis(BaseModel):
    """Structured investment hypothesis, grounded in retrieved passages."""
    hypothesis_id: str
    asset: str
    classification: Classification
    rationale: str                             # brief reasoning behind classification
    statement: str                              # concise opportunity/risk statement
    supporting_evidence: List[str]
    time_horizon: TimeHorizon
    confidence_score: int = Field(ge=0, le=100)
    grounding_passage_ids: List[str]            # links back to RetrievedPassage.passage_id
    created_at: datetime
    source_event_id: Optional[str] = None       # links back to NormalizedEvent.event_id


# 2.4 Decision Synthesis & Alerting

class DecisionArtefact(BaseModel):
    """The final structured output shown in the UI."""
    artefact_id: str
    asset: str
    action: Action
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: ConfidenceLevel
    evidence_bullets: List[str]                 # 2-3 bullets, per spec
    risk_flags: List[str]                       # contradictory signals / data gaps
    created_at: datetime
    alert_triggered: bool
    source_hypothesis_id: Optional[str] = None  # links back to Hypothesis.hypothesis_id


# 5.4 Observability — required trace log

class TraceEvent(BaseModel):
    """One row of the required agent trace log: which agent, what it did, what it returned."""
    event_id: str
    agent: AgentName
    action: str                                  # short description, e.g. "normalize_signal"
    tool_calls: List[str] = Field(default_factory=list)
    input_summary: str = ""
    output_summary: str = ""
    timestamp: datetime
    status: Literal["ok", "error", "fallback"] = "ok"
    error_message: Optional[str] = None


def new_trace_event(
    agent: AgentName,
    action: str,
    input_summary: str = "",
    output_summary: str = "",
    tool_calls: Optional[List[str]] = None,
    status: Literal["ok", "error", "fallback"] = "ok",
    error_message: Optional[str] = None,
) -> TraceEvent:
    """Convenience constructor so every node logs traces the same way."""
    return TraceEvent(
        event_id=str(uuid.uuid4()),
        agent=agent,
        action=action,
        tool_calls=tool_calls or [],
        input_summary=input_summary,
        output_summary=output_summary,
        timestamp=datetime.now(timezone.utc),
        status=status,
        error_message=error_message,
    )


# The shared LangGraph state object

class FinAgentState(TypedDict, total=False):
    """
    Passed between every LangGraph node. total=False because not every
    field is populated at every step of the pipeline (e.g. `artefact` only
    exists after the Decision Agent runs).
    """

    # --- Ingestion Agent I/O ---
    raw_signal: Optional[RawSignal]
    normalized_event: Optional[NormalizedEvent]

    # --- Retrieval Agent I/O ---
    rag_query: Optional[str]
    retrieved_passages: List[RetrievedPassage]

    # --- Analysis Agent I/O ---
    hypothesis: Optional[Hypothesis]

    # --- Decision Agent I/O ---
    artefact: Optional[DecisionArtefact]
    alert_threshold: int                          # configurable, default 70 per spec 5.3

    # --- Observability (accumulates across every node call, never overwritten) ---
    trace_log: Annotated[List[TraceEvent], operator.add]
    errors: Annotated[List[str], operator.add]


def create_initial_state(alert_threshold: int = 70) -> FinAgentState:
    """Factory for a clean starting state — use this at the top of a pipeline run."""
    return FinAgentState(
        raw_signal=None,
        normalized_event=None,
        rag_query=None,
        retrieved_passages=[],
        hypothesis=None,
        artefact=None,
        alert_threshold=alert_threshold,
        trace_log=[],
        errors=[],
    )