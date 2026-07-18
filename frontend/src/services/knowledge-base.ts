import api from './api'
import type { KnowledgeBaseStatus, RetrievedPassage, IngestionStatus } from '@/types/api'

export async function getStatus(): Promise<KnowledgeBaseStatus> {
  const { data } = await api.get<KnowledgeBaseStatus>('/knowledge-base/status')
  return data
}

export async function uploadDocuments(files: File[]): Promise<{ message: string; ingestion_id: string }> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const { data } = await api.post('/knowledge-base/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getIngestionStatus(id: string): Promise<IngestionStatus> {
  const { data } = await api.get<IngestionStatus>(`/knowledge-base/ingestions/${id}`)
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

export async function search(query: string): Promise<{ results: RetrievedPassage[] }> {
  const { data } = await api.get<{ results: RetrievedPassage[] }>('/knowledge-base/search', { params: { query } })
  return data
}
