import api from './api'
import type { RawSignal, PriceTickRequest, NewsRequest, PipelineResponse, NormalizedEvent } from '@/types/api'

export async function processSignal(signal: RawSignal): Promise<PipelineResponse> {
  const { data } = await api.post<PipelineResponse>('/signals/process', signal)
  return data
}

export async function processPriceTick(request: PriceTickRequest): Promise<PipelineResponse> {
  const { data } = await api.post<PipelineResponse>('/signals/price-tick', request)
  return data
}

export async function processNews(request: NewsRequest): Promise<PipelineResponse> {
  const { data } = await api.post<PipelineResponse>('/signals/news', request)
  return data
}

export async function uploadDocument(file: File, docType: string, asset?: string): Promise<PipelineResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', docType)
  if (asset) formData.append('asset', asset)
  const { data } = await api.post<PipelineResponse>('/signals/document', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getRecentSignals(limit = 10): Promise<{ items: NormalizedEvent[]; total: number }> {
  const { data } = await api.get('/signals/recent', { params: { limit } })
  return data
}
