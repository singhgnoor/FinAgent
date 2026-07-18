import api from './api'
import type { RawSignal, PriceTickRequest, NewsRequest, PipelineResponse, NormalizedEvent, PipelineJob } from '@/types/api'

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

export async function startPriceTickJob(request: PriceTickRequest): Promise<{ job_id: string; signal_id: string }> {
  const { data } = await api.post<{ job_id: string; signal_id: string }>('/signals/price-tick/jobs', request)
  return data
}

export async function startNewsJob(request: NewsRequest): Promise<{ job_id: string; signal_id: string }> {
  const { data } = await api.post<{ job_id: string; signal_id: string }>('/signals/news/jobs', request)
  return data
}

export async function getPipelineJob(id: string): Promise<PipelineJob> {
  const { data } = await api.get<PipelineJob>(`/signals/jobs/${id}`)
  return data
}

export async function getLatestPipelineJob(): Promise<PipelineJob | null> {
  const { data } = await api.get<{ job: PipelineJob | null }>('/signals/jobs/latest')
  return data.job
}

export async function getMarketData(ticker: string): Promise<PriceTickRequest & { source: string }> {
  const { data } = await api.get(`/signals/market-data/${encodeURIComponent(ticker)}`)
  return data
}
