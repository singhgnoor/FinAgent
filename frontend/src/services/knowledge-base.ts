import api from './api'
import type { KnowledgeBaseStatus } from '@/types/api'

export async function getStatus(): Promise<KnowledgeBaseStatus> {
  const { data } = await api.get<KnowledgeBaseStatus>('/knowledge-base/status')
  return data
}

export async function uploadDocuments(files: File[]): Promise<{ message: string; count: number }> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const { data } = await api.post('/knowledge-base/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteDocument(docName: string): Promise<{ message: string }> {
  const { data } = await api.delete(`/knowledge-base/documents/${encodeURIComponent(docName)}`)
  return data
}

export async function reindex(): Promise<{ message: string }> {
  const { data } = await api.post('/knowledge-base/reindex')
  return data
}

export async function search(query: string): Promise<{ results: Array<{ content: string; source: string; score: number }> }> {
  const { data } = await api.get('/knowledge-base/search', { params: { query } })
  return data
}
