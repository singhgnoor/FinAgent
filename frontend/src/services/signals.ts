import api from './api'
import type { RawSignal, PriceTickRequest, NewsRequest, PipelineResponse } from '@/types/api'

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
