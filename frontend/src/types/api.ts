export enum SignalType {
  PRICE_TICK = 'price_tick',
  NEWS_TEXT = 'news_text',
  DOCUMENT = 'document',
}

export enum Classification {
  BULLISH = 'bullish',
  BEARISH = 'bearish',
  NEUTRAL = 'neutral',
}

export enum Action {
  BUY = 'BUY',
  SELL = 'SELL',
  HOLD = 'HOLD',
  WATCH = 'WATCH',
}

export enum ConfidenceLevel {
  HIGH = 'High',
  MEDIUM = 'Medium',
  LOW = 'Low',
}

export enum TimeHorizon {
  INTRADAY = 'intraday',
  SHORT_TERM = 'short_term',
  MEDIUM_TERM = 'medium_term',
}

export type AgentName = 'ingestion_agent' | 'retrieval_agent' | 'analysis_agent' | 'decision_agent'

export interface PriceData {
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface TextData {
  headline: string
  summary?: string
  full_text?: string
  source?: string
}

export interface DocumentData {
  doc_name: string
  doc_type: string
  content?: string
  file_path?: string
}

export interface RawSignal {
  asset: string
  signal_type: SignalType
  price_data?: PriceData
  text_data?: TextData
  document_data?: DocumentData
}

export interface NormalizedEvent {
  event_id: string
  event_type: SignalType
  asset?: string
  source: string
  ingested_at: string
  normalized_text: string
  timestamp: string
  price_data?: PriceData
  text_data?: TextData
  document_data?: DocumentData
}

export interface RetrievedPassage {
  passage_id: string
  text: string
  source_document: string
  section_reference?: string
  similarity_score: number
  retrieved_at: string
  source_type: 'kb_retrieved' | 'fallback_generic'
  grounded: boolean
  metadata: Record<string, unknown>
}

export interface Hypothesis {
  hypothesis_id: string
  asset: string
  classification: Classification
  rationale: string
  statement: string
  supporting_evidence: string[]
  confidence_score: number
  grounding_passage_ids: string[]
  created_at: string
  grounded: boolean
}

export interface DecisionArtefact {
  artefact_id: string
  asset: string
  action: Action
  confidence_score: number
  confidence_level: ConfidenceLevel
  evidence_bullets: string[]
  risk_flags: string[]
  llm_commentary?: string
  created_at: string
  alert_triggered: boolean
  source_hypothesis_id?: string
  source_hypothesis_ids: string[]
}

export interface TraceEvent {
  agent: AgentName
  status: string
  duration_ms: number
  input_summary: string
  output_summary: string
  raw_input?: Record<string, unknown>
  raw_output?: Record<string, unknown>
  action?: string
  tool_calls?: string[]
  timestamp?: string
  error_message?: string
}

export interface FinAgentState {
  status: string
  normalized_event?: NormalizedEvent
  retrieved_passages?: RetrievedPassage[]
  hypothesis?: Hypothesis
  decision?: DecisionArtefact
  trace?: TraceEvent[]
  error?: string
  timing?: Record<string, number>
}

export interface PipelineResponse {
  success: boolean
  signal_id: string
  normalized_event?: NormalizedEvent
  retrieved_passages: RetrievedPassage[]
  hypothesis?: Hypothesis
  decision?: DecisionArtefact
  trace_log: TraceEvent[]
  errors: string[]
  elapsed_ms: number
  chunks_indexed: number
  embedding_completed: boolean
}

export interface PriceTickRequest {
  asset: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface NewsRequest {
  asset: string
  headline: string
  summary?: string
  full_text?: string
}

export interface KnowledgeBaseStatus {
  total_documents: number
  total_chunks: number
  embedding_model: string
  index_ready: boolean
  dimensions: number
}

export interface SystemStatus {
  llm_configured: boolean
  llm_model: string
  vector_store_ready: boolean
  document_count: number
  embedding_model: string
  pipeline_available: boolean
  uptime_seconds: number
}

export interface SystemHealth {
  status: string
  timestamp: string
  version: string
  services: Record<string, boolean>
  checks: Record<string, string>
}

export interface DecisionHistoryEntry {
  artefact_id: string
  asset: string
  action: Action
  confidence_score: number
  confidence_level: ConfidenceLevel
  evidence_bullets: string[]
  risk_flags: string[]
  llm_commentary?: string
  created_at: string
  alert_triggered: boolean
  trace_log: TraceEvent[]
  errors: string[]
  normalized_event?: NormalizedEvent
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PipelineJob {
  job_id: string
  signal_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string
  result?: Partial<PipelineResponse>
  error?: string
  elapsed_ms?: number
}

export interface IngestionStatus {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string
  completed_chunks: number
  total_chunks: number
  error?: string
}

export type EditableConfig = Record<string, string | number>
