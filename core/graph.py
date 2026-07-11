"""
FinAgent — LangGraph Orchestration

Wires the four agent nodes into a single LangGraph StateGraph, with typed
conditional edges governing transitions (per problem statement section 4,
which explicitly calls for conditions like "confidence threshold, event
type" instead of unconditional edges where meaningful):

    START
      |
      v
  [ingestion] --(no valid normalized_event)--> END
      |
      v (valid normalized_event)
  [retrieval]
      |
      v
   [analysis] --(no hypothesis / confidence too low to act on)--> END
      |
      v (confidence >= MIN_HYPOTHESIS_CONFIDENCE)
   [decision]
      |
      v
     END

All inter-agent communication happens exclusively through the shared
FinAgentState object returned/consumed by each node — no agent module
imports or calls another agent module directly. That "no bypassing the
graph" constraint, what makes this file, not the agent files, the single
source of truth for how data flows.
"""

from langgraph.graph import END, START, StateGraph

from agents.analysis import analysis_node
from agents.decision import decision_node
from agents.ingestion import ingestion_node
from agents.retrieval import retrieval_node
from core.state import FinAgentState, RawSignal, create_initial_state

# Below this score a hypothesis is treated as noise — not worth turning
# into a decision artefact at all. This is a *different* knob from
# `alert_threshold` (used inside decision_node to decide whether to fire
# an alert on an artefact that already exists): this one decides whether
# Decision even runs.
MIN_HYPOTHESIS_CONFIDENCE = 20


# Conditional routing functions

def route_after_ingestion(state: FinAgentState) -> str:
    """
    Typed condition on event validity. Only proceed to Retrieval if
    Ingestion actually produced a usable NormalizedEvent — malformed or
    missing raw signals stop the pipeline here instead of a None
    propagating silently into every downstream node.
    """
    if state.get("normalized_event") is None:
        return "invalid_event"
    return "valid_event"


def route_after_analysis(state: FinAgentState) -> str:
    """
    Typed condition on confidence threshold. Hypotheses too weak to act
    on don't get synthesized into artefacts — this keeps low-signal noise
    out of the UI instead of emitting a WATCH card for every single event.
    """
    hypothesis = state.get("hypothesis")
    if hypothesis is None:
        return "no_hypothesis"
    if hypothesis.confidence_score < MIN_HYPOTHESIS_CONFIDENCE:
        return "low_confidence"
    return "actionable"


# Graph construction

def build_graph():
    """Build and compile the FinAgent StateGraph. Call once, reuse the result."""
    graph = StateGraph(FinAgentState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("decision", decision_node)

    graph.add_edge(START, "ingestion")

    graph.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {
            "valid_event": "retrieval",
            "invalid_event": END,
        },
    )

    # Retrieval always follows a valid event — the query is built directly
    # from normalized_event.normalized_text (see agents/retrieval.py), so
    # there's no meaningful branch here; an unconditional edge is correct.
    graph.add_edge("retrieval", "analysis")

    graph.add_conditional_edges(
        "analysis",
        route_after_analysis,
        {
            "actionable": "decision",
            "low_confidence": END,
            "no_hypothesis": END,
        },
    )

    graph.add_edge("decision", END)

    return graph.compile()


# Convenience runner — what main.py / ui/app.py should actually call

_compiled_graph = None


def get_compiled_graph():
    """Lazily build+cache the compiled graph so we don't recompile per signal."""
    # So builds only on 1st call
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_once(raw_signal: RawSignal, alert_threshold: int = 70) -> FinAgentState:
    """
    Run the compiled graph exactly once on a single RawSignal and return
    the final state (normalized_event, retrieved_passages, hypothesis,
    artifact, trace_log — whichever got populated before an END branch).
    """
    compiled = get_compiled_graph()
    initial_state = create_initial_state(alert_threshold=alert_threshold)
    initial_state["raw_signal"] = raw_signal
    return compiled.invoke(initial_state)