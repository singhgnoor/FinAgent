"""
Analysis Agent — Stub

Role (2.3): Classify the normalized event as bullish/bearish/neutral,
generate a structured investment hypothesis grounded in retrieved
passages, and assign a confidence score (0-100).

STUB: uses simple deterministic dummy logic instead of an LLM call.
Replace `_classify_and_score` with a real LangChain LLM chain that queries
the Retrieval Agent's results before finalizing the hypothesis.
"""

import uuid
from datetime import datetime, timezone

from core.state import (
    AgentName,
    Classification,
    FinAgentState,
    Hypothesis,
    TimeHorizon,
    new_trace_event,
)


def _classify_and_score(state: FinAgentState) -> Hypothesis:
    """STUB: fake classification. Replace with real LLM reasoning."""
    event = state["normalized_event"]
    passages = state.get("retrieved_passages", [])

    classification = Classification.NEUTRAL
    confidence_score = 55

    return Hypothesis(
        hypothesis_id=str(uuid.uuid4()),
        asset=event.asset or "UNKNOWN",
        classification=classification,
        rationale="Stub rationale: no real reasoning performed yet.",
        statement=f"Stub hypothesis for {event.asset or 'UNKNOWN'} "
                  f"based on '{event.normalized_text[:60]}'",
        supporting_evidence=[p.text[:80] for p in passages[:2]]
        or ["No supporting evidence retrieved."],
        time_horizon=TimeHorizon.SHORT_TERM,
        confidence_score=confidence_score,
        grounding_passage_ids=[p.passage_id for p in passages],
        created_at=datetime.now(timezone.utc),
        source_event_id=event.event_id,
    )


def analysis_node(state: FinAgentState) -> dict:
    """LangGraph node entrypoint. Produces a Hypothesis from state."""
    event = state.get("normalized_event")

    if event is None:
        trace = new_trace_event(
            agent=AgentName.ANALYSIS,
            action="skip_no_event",
            output_summary="no-op, no normalized_event in state",
            status="fallback",
        )
        return {"trace_log": [trace]}

    hypothesis = _classify_and_score(state)

    trace = new_trace_event(
        agent=AgentName.ANALYSIS,
        action="classify_and_generate_hypothesis",
        tool_calls=["retrieval_agent.query (via state)"],
        input_summary=event.normalized_text[:80],
        output_summary=f"hypothesis id={hypothesis.hypothesis_id}, "
                        f"confidence={hypothesis.confidence_score}",
    )

    return {
        "hypothesis": hypothesis,
        "trace_log": [trace],
    }