"""
Analysis Agent (2.3): Signal Analysis & Hypothesis Generation

Role (PS 2.3): classify the normalized event as bullish/bearish/neutral
with a brief rationale, generate a structured investment hypothesis
(statement, supporting evidence, time horizon), and assign a 0-100
confidence score based on signal strength and evidence quality. Must
query the Retrieval Agent's output (`retrieved_passages` in state) before
finalizing the hypothesis.

Design, mirrored from decision.py's conventions but adapted for a
different job:

- Decision Agent has a deterministic core (action/confidence come
  straight from the hypothesis) with an LLM-advisory layer bolted on
  top. Analysis has no such deterministic core: classification, the
  hypothesis statement, and time horizon are inherently judgment calls,
  so those come directly from the LLM via structured output
  (`_AnalysisOutput`, same `.with_structured_output()` pattern as
  `_DecisionAdvice`).
- The one place a deterministic signal belongs is the confidence score,
  since PS 2.3 explicitly ties it to "signal strength and evidence
  quality" - both of which have a measurable component independent of
  the LLM's read. `_evidence_strength_adjustment` computes a small,
  bounded nudge from passage count and average retrieval similarity,
  and `_blend_confidence` folds it into the LLM's own confidence
  judgment. The LLM's assessment still dominates; the adjustment just
  keeps it honest when evidence is thin or unusually strong.
- Grounding is enforced structurally, not just requested in the prompt:
  if `retrieved_passages` is empty, this node never calls the LLM at
  all - it skips hypothesis generation the same way `retrieval_node`
  skips search on an empty query. `grounding_passage_ids` is populated
  from every passage handed to the LLM (not an LLM-reported subset),
  since all of them were part of the grounding context it reasoned over.
- On LLM failure, unlike Decision Agent, there is no deterministic
  fallback to fall back to - a fabricated NEUTRAL/stub classification
  would be presented downstream as a real judgment it never was. So
  failure here returns no hypothesis and logs to `errors`, letting
  `route_after_analysis` send the run to the `no_hypothesis` END branch,
  the same failure shape `retrieval_node` already uses.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from core.llm import get_llm
from core.state import (
    AgentName,
    Classification,
    FinAgentState,
    Hypothesis,
    NormalizedEvent,
    RetrievedPassage,
    TimeHorizon,
    new_trace_event,
)


# Structured LLM output - judgment fields only. hypothesis_id,
# grounding_passage_ids, created_at, and source_event_id are filled in
# deterministically afterward, never by the model.

class _AnalysisOutput(BaseModel):
    """Structured LLM output for signal classification and hypothesis drafting."""
    classification: Classification = Field(
        description="Overall read on the event: bullish, bearish, or neutral."
    )
    rationale: str = Field(
        description="Brief reasoning behind the classification, referencing "
                    "specific retrieved evidence where relevant."
    )
    statement: str = Field(
        description="Concise statement of the investment opportunity or risk."
    )
    supporting_evidence: List[str] = Field(
        description="Specific evidence points drawn ONLY from the retrieved "
                    "passages provided below. Do not invent evidence not "
                    "present in the passages."
    )
    time_horizon: TimeHorizon = Field(
        description="Expected time horizon for this hypothesis to play out: "
                    "intraday, short_term (1-5 days), or medium_term (1-4 weeks)."
    )
    confidence_score: int = Field(
        ge=0, le=100,
        description="Your assessment (0-100) of signal strength and evidence "
                    "quality. Be conservative if the passages are weak, sparse, "
                    "or only tangentially related to the event."
    )


_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a financial signal analyst. Given a normalized market event and "
     "a set of retrieved supporting passages (each tagged with a passage id "
     "and source document), you must: (1) classify the event as bullish, "
     "bearish, or neutral with a brief rationale, (2) write a concise "
     "hypothesis statement of the opportunity or risk, (3) list specific "
     "supporting evidence drawn only from the passages given - never invent "
     "evidence, (4) assign a time horizon, and (5) assign a confidence score "
     "(0-100) reflecting signal strength and evidence quality. If the "
     "passages are weak, sparse, or only tangentially related, say so in the "
     "rationale and reflect it with a lower confidence score."),
    ("human",
     "Normalized event:\n"
     "Asset: {asset}\n"
     "Event type: {event_type}\n"
     "Text: {normalized_text}\n\n"
     "Retrieved passages (grounding evidence, cite by passage id):\n"
     "{passages_block}\n"),
])


def _build_passages_block(passages: List[RetrievedPassage]) -> str:
    """Format retrieved passages with source attribution for the prompt."""
    lines = []
    for p in passages:
        section = f", {p.section_reference}" if p.section_reference else ""
        lines.append(
            f"[{p.passage_id}] ({p.source_document}{section}, "
            f"similarity={p.similarity_score:.2f}): {p.text}"
        )
    return "\n".join(lines)


def _get_llm_analysis(
    event: NormalizedEvent, passages: List[RetrievedPassage]
) -> _AnalysisOutput:
    structured_llm = get_llm().with_structured_output(_AnalysisOutput)
    chain = _ANALYSIS_PROMPT | structured_llm
    return chain.invoke({
        "asset": event.asset or "UNKNOWN",
        "event_type": event.event_type.value,
        "normalized_text": event.normalized_text,
        "passages_block": _build_passages_block(passages),
    })


def _get_analysis_safe(
    event: NormalizedEvent, passages: List[RetrievedPassage]
) -> Tuple[Optional[_AnalysisOutput], str, Optional[str]]:
    """Never let an LLM failure crash the graph - report it, don't fake output."""
    try:
        return _get_llm_analysis(event, passages), "ok", None
    except Exception as e:
        return None, "error", str(e)


# Deterministic confidence adjustment - blended with the LLM's own score

def _evidence_strength_adjustment(passages: List[RetrievedPassage]) -> int:
    """
    Small, bounded nudge (-8 to +10) on top of the LLM's confidence
    judgment, from the *quantity* and *quality* of grounding evidence
    actually retrieved. The LLM's read of the reasoning still dominates;
    this keeps confidence honest when the LLM sounds confident but
    evidence is thin, or conservative when evidence is unusually strong.

    Deliberately does not attempt contradictory-passage detection (i.e.
    comparing stance across passages) - that needs its own classification
    step and would add noise rather than signal without one. Left as a
    future enhancement, not a heuristic guess.
    """
    count = len(passages)
    avg_similarity = sum(p.similarity_score for p in passages) / count

    if count >= 5:
        count_bonus = 6
    elif count >= 3:
        count_bonus = 3
    else:
        count_bonus = 0

    if avg_similarity >= 0.80:
        similarity_bonus = 4
    elif avg_similarity >= 0.60:
        similarity_bonus = 1
    else:
        similarity_bonus = -8

    return count_bonus + similarity_bonus


def _blend_confidence(llm_score: int, adjustment: int) -> int:
    return max(0, min(100, llm_score + adjustment))


def analysis_node(state: FinAgentState) -> dict:
    """LangGraph node entrypoint. Produces a Hypothesis from state, or skips."""
    event = state.get("normalized_event")

    if event is None:
        trace = new_trace_event(
            agent=AgentName.ANALYSIS,
            action="skip_no_event",
            output_summary="no-op, no normalized_event in state",
            status="fallback",
        )
        return {"trace_log": [trace]}

    passages = state.get("retrieved_passages", [])

    if not passages:
        # PS 2.3 requires grounding before finalizing a hypothesis - with
        # nothing retrieved there is nothing to ground on, so this node
        # doesn't call the LLM at all. route_after_analysis sends this to
        # the no_hypothesis END branch, same as the LLM-failure path below.
        trace = new_trace_event(
            agent=AgentName.ANALYSIS,
            action="skip_no_grounding",
            input_summary=event.normalized_text[:80],
            output_summary="no-op, retrieved_passages is empty - "
                            "cannot ground a hypothesis",
            status="fallback",
        )
        return {"trace_log": [trace]}

    output, status, error = _get_analysis_safe(event, passages)

    if output is None:
        trace = new_trace_event(
            agent=AgentName.ANALYSIS,
            action="classify_and_generate_hypothesis",
            tool_calls=["llm.analysis_classification (failed)"],
            input_summary=event.normalized_text[:80],
            output_summary="no-op, LLM classification failed",
            status="error",
            error_message=error,
        )
        return {
            "trace_log": [trace],
            "errors": [f"analysis_agent: llm classification failed - {error}"],
        }

    adjustment = _evidence_strength_adjustment(passages)
    final_confidence = _blend_confidence(output.confidence_score, adjustment)

    hypothesis = Hypothesis(
        hypothesis_id=str(uuid.uuid4()),
        asset=event.asset or "UNKNOWN",
        classification=output.classification,
        rationale=output.rationale,
        statement=output.statement,
        supporting_evidence=output.supporting_evidence or ["No specific evidence cited."],
        time_horizon=output.time_horizon,
        confidence_score=final_confidence,
        grounding_passage_ids=[p.passage_id for p in passages],
        created_at=datetime.now(timezone.utc),
        source_event_id=event.event_id,
    )

    trace = new_trace_event(
        agent=AgentName.ANALYSIS,
        action="classify_and_generate_hypothesis",
        tool_calls=["retrieval_agent.query (via state)", "llm.analysis_classification"],
        input_summary=event.normalized_text[:80],
        output_summary=(
            f"hypothesis id={hypothesis.hypothesis_id}, "
            f"classification={hypothesis.classification.value}, "
            f"llm_confidence={output.confidence_score}, "
            f"evidence_adjustment={adjustment:+d}, "
            f"final_confidence={final_confidence}"
        ),
        status="ok",
    )

    return {"hypothesis": hypothesis, "trace_log": [trace]}