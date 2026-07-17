import api from './api'
import type { DecisionHistoryEntry, PaginatedResponse } from '@/types/api'

export async function getDecisions(params?: {
  page?: number
  page_size?: number
  asset?: string
  action?: string
}): Promise<PaginatedResponse<DecisionHistoryEntry>> {
  const { data } = await api.get<PaginatedResponse<DecisionHistoryEntry>>('/decisions', { params })
  return data
}

export async function getDecision(id: string): Promise<DecisionHistoryEntry> {
  const { data } = await api.get<DecisionHistoryEntry>(`/decisions/${id}`)
  return data
}
