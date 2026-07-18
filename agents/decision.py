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
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from core.llm import get_llm
from core.log import get_logger
from core.state import (
    Action,
    AgentName,
    Classification,
    DecisionArtefact,
    FinAgentState,
    confidence_to_level,
    new_trace_event,
)

logger = get_logger(__name__)

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
    logger.info(
        f"[decision.llm] Calling LLM risk advisory: model=gpt-5.4-mini, "
        f"asset={hypothesis.asset}, classification={hypothesis.classification.value}, "
        f"confidence={hypothesis.confidence_score}"
    )
    logger.debug(f"[decision.llm] Hypothesis statement: {hypothesis.statement[:150]}")
    
    llm_start = time.perf_counter()
    structured_llm = get_llm().with_structured_output(_DecisionAdvice)
    evidence_text = "\n".join(f"- {e}" for e in hypothesis.supporting_evidence) or "- none"
    chain = _ADVICE_PROMPT | structured_llm
    
    try:
        result = chain.invoke({
            "asset": hypothesis.asset,
            "classification": hypothesis.classification.value,
            "rationale": hypothesis.rationale,
            "statement": hypothesis.statement,
            "time_horizon": hypothesis.time_horizon.value,
            "confidence_score": hypothesis.confidence_score,
            "evidence": evidence_text,
        })
        
        elapsed = time.perf_counter() - llm_start
        logger.info(
            f"[decision.llm] LLM advisory completed in {elapsed:.2f}s: "
            f"risk_flags={len(result.risk_flags)}, "
            f"commentary_preview={result.commentary[:100]}"
        )
        logger.debug(f"[decision.llm] Risk flags: {result.risk_flags}")
        logger.debug(f"[decision.llm] Commentary: {result.commentary}")
        
        return result
    except Exception as e:
        logger.exception(f"[decision.llm] LLM advisory call failed: {type(e).__name__}: {str(e)}")
        raise


def _get_llm_advice_safe(hypothesis) -> Tuple[Optional[_DecisionAdvice], str, Optional[str]]:
    """Never let an LLM failure break the deterministic decision pipeline."""
    try:
        return _get_llm_advice(hypothesis), "ok", None
    except Exception as e:
        return None, "fallback", str(e)


def _action_from_hypotheses(hypotheses: List) -> Action:
    """Choose a reachable action from aggregate direction and conviction.

    HOLD is deliberate: neutral/mixed evidence at usable confidence means keep
    the existing position rather than treating uncertainty as WATCH.  WATCH is
    reserved for low-conviction directional signals needing more confirmation.
    """
    classifications = {h.classification for h in hypotheses}
    confidence = sum(h.confidence_score for h in hypotheses) / len(hypotheses)
    mixed_direction = (
        Classification.BULLISH in classifications and Classification.BEARISH in classifications
    )
    if mixed_direction or classifications == {Classification.NEUTRAL}:
        return Action.HOLD if confidence >= 40 else Action.WATCH
    direction = next(iter(classifications))
    if confidence < 60:
        return Action.WATCH
    return Action.BUY if direction == Classification.BULLISH else Action.SELL


def _synthesize_artefact(state: FinAgentState, advice: Optional[_DecisionAdvice]) -> DecisionArtefact:
    primary = state["hypothesis"]
    hypotheses = state.get("hypotheses") or [primary]
    hypotheses = [h for h in hypotheses if h.asset == primary.asset] or [primary]
    threshold = state.get("alert_threshold", 70)

    classifications = {h.classification for h in hypotheses}
    contradictory = Classification.BULLISH in classifications and Classification.BEARISH in classifications
    confidence = round(sum(h.confidence_score for h in hypotheses) / len(hypotheses))
    if contradictory:
        confidence = max(0, confidence - 15)
    if any(not h.grounded for h in hypotheses):
        confidence = min(confidence, 39)
    action = _action_from_hypotheses(hypotheses)
    confidence_level = confidence_to_level(confidence)
    evidence = []
    for hypothesis in hypotheses:
        for item in hypothesis.supporting_evidence:
            if item not in evidence:
                evidence.append(item)

    if advice is not None:
        risk_flags = advice.risk_flags or ["LLM returned no risk flags."]
        llm_commentary = advice.commentary
    else:
        risk_flags = ["LLM risk advisory unavailable — deterministic artefact only."]
        llm_commentary = None
    if contradictory:
        risk_flags.append("Contradictory bullish and bearish hypotheses in the analysis window.")
    if any(not h.grounded for h in hypotheses):
        risk_flags.append("One or more hypotheses used non-KB fallback context; confidence capped.")

    return DecisionArtefact(
        artefact_id=str(uuid.uuid4()),
        asset=primary.asset,
        action=action,
        confidence_score=confidence,
        confidence_level=confidence_level,
        evidence_bullets=evidence[:3] or ["No evidence available."],
        risk_flags=risk_flags,
        llm_commentary=llm_commentary,
        created_at=datetime.now(timezone.utc),
        alert_triggered=confidence > threshold,
        source_hypothesis_id=primary.hypothesis_id,
        source_hypothesis_ids=[h.hypothesis_id for h in hypotheses],
    )


def decision_node(state: FinAgentState) -> dict:
    """LangGraph node entrypoint. Produces the final DecisionArtefact."""
    node_start = time.perf_counter()
    hypothesis = state.get("hypothesis")

    logger.info("[decision] Node entry: checking for hypothesis")

    if hypothesis is None:
        elapsed = time.perf_counter() - node_start
        logger.warning("[decision] Skipping: no hypothesis in state")
        trace = new_trace_event(
            agent=AgentName.DECISION,
            action="skip_no_hypothesis",
            output_summary="no-op, no hypothesis in state",
            duration_ms=round(elapsed * 1000, 2),
            status="fallback",
        )
        logger.debug(f"[decision] Trace event: {trace.model_dump_json()}")
        return {"trace_log": [trace]}

    logger.info(
        f"[decision] Hypothesis details: asset={hypothesis.asset}, "
        f"classification={hypothesis.classification.value}, "
        f"confidence={hypothesis.confidence_score}"
    )

    advice, advice_status, advice_error = _get_llm_advice_safe(hypothesis)
    
    # Log deterministic rule result
    deterministic_action = _action_from_hypotheses(state.get("hypotheses") or [hypothesis])
    logger.info(
        f"[decision] Deterministic rule: classification={hypothesis.classification.value} "
        f"-> action={deterministic_action.value}"
    )
    
    # Log LLM advisory result
    if advice:
        logger.info(
            f"[decision] LLM advisory status: ok, "
            f"risk_flags={len(advice.risk_flags)}"
        )
    else:
        logger.warning(
            f"[decision] LLM advisory status: fallback - {advice_error}"
        )
    
    artefact = _synthesize_artefact(state, advice)

    elapsed = time.perf_counter() - node_start

    trace = new_trace_event(
        agent=AgentName.DECISION,
        action="synthesize_artefact",
        tool_calls=["llm.decision_advice"] if advice is not None else ["llm.decision_advice (failed)"],
        input_summary=f"hypothesis id={hypothesis.hypothesis_id}",
        output_summary=f"artefact id={artefact.artefact_id}, "
                        f"action={artefact.action.value}, alert={artefact.alert_triggered}",
        duration_ms=round(elapsed * 1000, 2),
        status=advice_status,
        error_message=advice_error,
    )

    # Log the final DecisionArtefact
    logger.info(
        f"[decision] FINAL DECISION ARTEFACT: asset={artefact.asset}, "
        f"action={artefact.action.value}, confidence={artefact.confidence_score}, "
        f"confidence_level={artefact.confidence_level.value}, "
        f"alert_triggered={artefact.alert_triggered}"
    )
    logger.debug(
        f"[decision] Artefact details: id={artefact.artefact_id}, "
        f"evidence_bullets={artefact.evidence_bullets}, "
        f"risk_flags={artefact.risk_flags}"
    )
    if artefact.llm_commentary:
        logger.debug(f"[decision] LLM commentary: {artefact.llm_commentary}")
    
    logger.info(f"[decision] Node exit: elapsed={elapsed:.3f}s")
    logger.debug(f"[decision] Trace event: {trace.model_dump_json()}")

    if artefact.alert_triggered:
        logger.warning(
            f"[ALERT] {artefact.asset} -> {artefact.action.value} "
            f"(confidence {artefact.confidence_score}, {artefact.confidence_level.value})"
        )
        print(
            f"ALERT: {artefact.asset} -> {artefact.action.value} "
            f"(confidence {artefact.confidence_score}, {artefact.confidence_level.value})"
        )

    result = {"artefact": artefact, "trace_log": [trace]}
    if advice_error:
        result["errors"] = [f"decision_agent: llm advisory failed - {advice_error}"]
    return result
