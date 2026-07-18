import { useMutation, useQuery } from '@tanstack/react-query'
import { processSignal, processPriceTick, processNews, uploadDocument, getLatestPipelineJob, getRecentSignals } from '@/services/signals'
import type { RawSignal, PriceTickRequest, NewsRequest } from '@/types/api'

export function useSignalMutation() {
  return useMutation({
    mutationFn: (signal: RawSignal) => processSignal(signal),
  })
}

export function usePriceTickMutation() {
  return useMutation({
    mutationFn: (request: PriceTickRequest) => processPriceTick(request),
  })
}

export function useNewsMutation() {
  return useMutation({
    mutationFn: (request: NewsRequest) => processNews(request),
  })
}

export function useDocumentMutation() {
  return useMutation({ mutationFn: ({ file, docType, asset }: { file: File; docType: string; asset?: string }) => uploadDocument(file, docType, asset) })
}

export function useRecentSignals() {
  return useQuery({ queryKey: ['recent-signals'], queryFn: () => getRecentSignals(), refetchInterval: 5000 })
}

export function useLatestPipelineJob() {
  return useQuery({ queryKey: ['pipeline-job', 'latest'], queryFn: getLatestPipelineJob, refetchInterval: 800 })
}
