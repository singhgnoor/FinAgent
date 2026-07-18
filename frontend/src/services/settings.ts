import api from './api'
import type { EditableConfig } from '@/types/api'

export async function getConfig(): Promise<{ values: EditableConfig; editable: string[] }> {
  const { data } = await api.get('/config')
  return data
}

export async function saveConfig(values: EditableConfig): Promise<{ values: EditableConfig; message: string }> {
  const { data } = await api.put('/config', { values })
  return data
}
