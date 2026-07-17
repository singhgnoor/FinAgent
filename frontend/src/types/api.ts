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

export enum AgentName {
  INGESTION = 'ingestion_agent',
  RETRIEVAL = 'retrieval_agent',
  ANALYSIS = 'analysis_agent',
  DECISION = 'decision_agent',
}

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
  asset: string
  signal_type: SignalType
  normalized_features: Record<string, number>
  raw_text?: string
  timestamp: string
}

export interface RetrievedPassage {
  content: string
  source: string
  relevance_score: number
}

export interface Hypothesis {
  classification: Classification
  confidence: number
  reasoning: string
  supporting_evidence: string[]
}

export interface DecisionArtefact {
  action: Action
  confidence_level: ConfidenceLevel
  confidence_score: number
  risk_level: string
  time_horizon: TimeHorizon
  reasoning: string
  commentary: string
  alert: boolean
  alert_reason?: string
  risk_flags: string[]
}

export interface TraceEvent {
  agent: AgentName
  status: string
  duration_ms: number
  input_summary: string
  output_summary: string
  raw_input?: Record<string, unknown>
  raw_output?: Record<string, unknown>
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
  status: string
  state: FinAgentState
  decision_id?: string
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
  decision_id: string
  timestamp: string
  asset: string
  signal_type: SignalType
  action: Action
  confidence: number
  confidence_level: ConfidenceLevel
  risk_level: string
  time_horizon: TimeHorizon
  alert: boolean
  alert_reason?: string
  reasoning: string
  risk_flags: string[]
  evidence: RetrievedPassage[]
  trace: TraceEvent[]
  commentary: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
