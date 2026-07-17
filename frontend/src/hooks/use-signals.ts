import { useMutation } from '@tanstack/react-query'
import { processSignal, processPriceTick, processNews } from '@/services/signals'
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
