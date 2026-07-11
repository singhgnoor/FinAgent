"""
Decision Synthesis & Alerting Agent — Stub

Role (2.4): Aggregate the hypothesis into a structured decision artifact
(action, confidence level, evidence, risk flags) and trigger an alert if
confidence exceeds the configured threshold (default 70, see spec 5.3).

STUB: simple deterministic mapping from hypothesis -> artifact. Replace
`_synthesize_artefact` with richer aggregation logic later (e.g. combining
multiple hypotheses for the same asset over time).
"""

import uuid
from datetime import datetime, timezone

from core.state import (
    Action,
    AgentName,
    Classification,
    DecisionArtefact,
    FinAgentState,
    confidence_to_level,
    new_trace_event,
)


def _action_from_classification(classification: Classification) -> Action:
    return {
        Classification.BULLISH: Action.BUY,
        Classification.BEARISH: Action.SELL,
        Classification.NEUTRAL: Action.WATCH,
    }[classification]


def _synthesize_artefact(state: FinAgentState) -> DecisionArtefact:
    hypothesis = state["hypothesis"]
    threshold = state.get("alert_threshold", 70)

    action = _action_from_classification(hypothesis.classification)
    confidence_level = confidence_to_level(hypothesis.confidence_score)

    return DecisionArtefact(
        artefact_id=str(uuid.uuid4()),
        asset=hypothesis.asset,
        action=action,
        confidence_score=hypothesis.confidence_score,
        confidence_level=confidence_level,
        evidence_bullets=hypothesis.supporting_evidence[:3]
        or ["No evidence available (stub)."],
        risk_flags=["Stub artefact: no real risk analysis performed yet."],
        created_at=datetime.now(timezone.utc),
        alert_triggered=hypothesis.confidence_score > threshold,
        source_hypothesis_id=hypothesis.hypothesis_id,
    )


def decision_node(state: FinAgentState) -> dict:
    """LangGraph node entrypoint. Produces the final DecisionArtefact."""
    hypothesis = state.get("hypothesis")

    if hypothesis is None:
        trace = new_trace_event(
            agent=AgentName.DECISION,
            action="skip_no_hypothesis",
            output_summary="no-op, no hypothesis in state",
            status="fallback",
        )
        return {"trace_log": [trace]}

    artefact = _synthesize_artefact(state)

    trace = new_trace_event(
        agent=AgentName.DECISION,
        action="synthesize_artefact",
        input_summary=f"hypothesis id={hypothesis.hypothesis_id}",
        output_summary=f"artefact id={artefact.artefact_id}, "
                        f"action={artefact.action.value}, alert={artefact.alert_triggered}",
    )

    if artefact.alert_triggered:
        print(
            f"ALERT: {artefact.asset} -> {artefact.action.value} "
            f"(confidence {artefact.confidence_score}, {artefact.confidence_level.value})"
        )

    return {
        "artefact": artefact,
        "trace_log": [trace],
    }