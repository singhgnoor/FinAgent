from typing import List, Optional

from pydantic import BaseModel

from core.state import (
    DecisionArtefact,
    Hypothesis,
    NormalizedEvent,
    RetrievedPassage,
    TraceEvent,
)


class PipelineResponse(BaseModel):
    success: bool
    signal_id: str
    normalized_event: Optional[NormalizedEvent] = None
    retrieved_passages: List[RetrievedPassage] = []
    hypothesis: Optional[Hypothesis] = None
    decision: Optional[DecisionArtefact] = None
    trace_log: List[TraceEvent] = []
    errors: List[str] = []
    elapsed_ms: float
