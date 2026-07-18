from typing import List, Optional

from pydantic import BaseModel, Field

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
    retrieved_passages: List[RetrievedPassage] = Field(default_factory=list)
    hypothesis: Optional[Hypothesis] = None
    decision: Optional[DecisionArtefact] = None
    trace_log: List[TraceEvent] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    elapsed_ms: float
    chunks_indexed: int = 0
    embedding_completed: bool = False
