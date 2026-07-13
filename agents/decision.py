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
from typing import List, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from core.llm import get_llm
from core.state import (
    Action,
    AgentName,
    Classification,
    DecisionArtefact,
    FinAgentState,
    confidence_to_level,
    new_trace_event,
)

class _DecisionAdvice(BaseModel):
    """Structured LLM output — advisory only, never decides action/confidence."""
    risk_flags: List[str] = Field(
        description="2-4 specific contradictory signals or data gaps that should "
                    "lower confidence in this hypothesis. Be concrete, not generic."
    )
    commentary: str = Field(
        description="1-2 sentence advisory note a human trader should read before "
                    "acting on this decision."
    )


_ADVICE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a risk-aware financial analyst reviewing an automated trading "
     "hypothesis before it is finalized. You do NOT decide the action — that "
     "is already fixed elsewhere. Your only job is to (1) flag contradictory "
     "signals or data gaps that should lower confidence, and (2) give a short "
     "advisory note. Be specific and skeptical; do not just restate the hypothesis."),
    ("human",
     "Asset: {asset}\n"
     "Classification: {classification}\n"
     "Rationale: {rationale}\n"
     "Statement: {statement}\n"
     "Time horizon: {time_horizon}\n"
     "Confidence score: {confidence_score}/100\n"
     "Supporting evidence:\n{evidence}\n"),
])


def _get_llm_advice(hypothesis) -> _DecisionAdvice:
    structured_llm = get_llm().with_structured_output(_DecisionAdvice)
    evidence_text = "\n".join(f"- {e}" for e in hypothesis.supporting_evidence) or "- none"
    chain = _ADVICE_PROMPT | structured_llm
    return chain.invoke({
        "asset": hypothesis.asset,
        "classification": hypothesis.classification.value,
        "rationale": hypothesis.rationale,
        "statement": hypothesis.statement,
        "time_horizon": hypothesis.time_horizon.value,
        "confidence_score": hypothesis.confidence_score,
        "evidence": evidence_text,
    })


def _get_llm_advice_safe(hypothesis) -> Tuple[Optional[_DecisionAdvice], str, Optional[str]]:
    """Never let an LLM failure break the deterministic decision pipeline."""
    try:
        return _get_llm_advice(hypothesis), "ok", None
    except Exception as e:
        return None, "fallback", str(e)


def _action_from_classification(classification: Classification) -> Action:
    return {
        Classification.BULLISH: Action.BUY,
        Classification.BEARISH: Action.SELL,
        Classification.NEUTRAL: Action.WATCH,
    }[classification]


def _synthesize_artefact(state: FinAgentState, advice: Optional[_DecisionAdvice]) -> DecisionArtefact:
    hypothesis = state["hypothesis"]
    threshold = state.get("alert_threshold", 70)

    action = _action_from_classification(hypothesis.classification)
    confidence_level = confidence_to_level(hypothesis.confidence_score)

    if advice is not None:
        risk_flags = advice.risk_flags or ["LLM returned no risk flags."]
        llm_commentary = advice.commentary
    else:
        risk_flags = ["LLM risk advisory unavailable — deterministic artefact only."]
        llm_commentary = None

    return DecisionArtefact(
        artefact_id=str(uuid.uuid4()),
        asset=hypothesis.asset,
        action=action,
        confidence_score=hypothesis.confidence_score,
        confidence_level=confidence_level,
        evidence_bullets=hypothesis.supporting_evidence[:3] or ["No evidence available."],
        risk_flags=risk_flags,
        llm_commentary=llm_commentary,
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

    advice, advice_status, advice_error = _get_llm_advice_safe(hypothesis)
    artefact = _synthesize_artefact(state, advice)

    trace = new_trace_event(
        agent=AgentName.DECISION,
        action="synthesize_artefact",
        tool_calls=["llm.decision_advice"] if advice is not None else ["llm.decision_advice (failed)"],
        input_summary=f"hypothesis id={hypothesis.hypothesis_id}",
        output_summary=f"artefact id={artefact.artefact_id}, "
                        f"action={artefact.action.value}, alert={artefact.alert_triggered}",
        status=advice_status,
        error_message=advice_error,
    )

    if artefact.alert_triggered:
        print(
            f"ALERT: {artefact.asset} -> {artefact.action.value} "
            f"(confidence {artefact.confidence_score}, {artefact.confidence_level.value})"
        )

    result = {"artefact": artefact, "trace_log": [trace]}
    if advice_error:
        result["errors"] = [f"decision_agent: llm advisory failed - {advice_error}"]
    return result