import { useQuery } from '@tanstack/react-query'
import { getHealth, getStatus } from '@/services/system'

export function useSystemHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: getHealth,
    refetchInterval: 15000,
  })
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: getStatus,
    refetchInterval: 15000,
  })
}
