import { useQuery } from '@tanstack/react-query'
import { getDecisions, getDecision } from '@/services/decisions'

export function useDecisions(params?: {
  page?: number
  page_size?: number
  asset?: string
  action?: string
  alerted?: boolean
}) {
  return useQuery({
    queryKey: ['decisions', params],
    queryFn: () => getDecisions(params),
  })
}

export function useDecision(id: string | undefined) {
  return useQuery({
    queryKey: ['decisions', id],
    queryFn: () => getDecision(id!),
    enabled: !!id,
  })
}
