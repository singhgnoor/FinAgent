export const THEME = {
  BUY: '#22c55e',
  SELL: '#ef4444',
  HOLD: '#f59e0b',
  WATCH: '#f59e0b',
  BULLISH: '#22c55e',
  BEARISH: '#ef4444',
  NEUTRAL: '#64748b',
  HIGH_CONFIDENCE: '#22c55e',
  MEDIUM_CONFIDENCE: '#f59e0b',
  LOW_CONFIDENCE: '#ef4444',
} as const

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  price_tick: 'Price Tick',
  news_text: 'News',
  document: 'Document',
}

export const ACTION_LABELS: Record<string, string> = {
  BUY: 'Buy',
  SELL: 'Sell',
  HOLD: 'Hold',
  WATCH: 'Watch',
}

export const AGENT_LABELS: Record<string, string> = {
  ingestion_agent: 'Ingestion',
  retrieval_agent: 'Retrieval',
  analysis_agent: 'Analysis',
  decision_agent: 'Decision',
}
