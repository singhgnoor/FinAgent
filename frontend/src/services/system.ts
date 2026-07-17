import api from './api'
import type { SystemHealth, SystemStatus } from '@/types/api'

export async function getHealth(): Promise<SystemHealth> {
  const { data } = await api.get<SystemHealth>('/health')
  return data
}

export async function getStatus(): Promise<SystemStatus> {
  const { data } = await api.get<SystemStatus>('/status')
  return data
}
