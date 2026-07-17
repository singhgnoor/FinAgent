import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getStatus, uploadDocuments, deleteDocument, reindex, search } from '@/services/knowledge-base'

export function useKnowledgeBaseStatus() {
  return useQuery({
    queryKey: ['knowledge-base', 'status'],
    queryFn: getStatus,
    refetchInterval: 30000,
  })
}

export function useUploadDocuments() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => uploadDocuments(files),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge-base'] })
    },
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docName: string) => deleteDocument(docName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge-base'] })
    },
  })
}

export function useReindex() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: reindex,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge-base'] })
    },
  })
}

export function useKBSearch(query: string) {
  return useQuery({
    queryKey: ['knowledge-base', 'search', query],
    queryFn: () => search(query),
    enabled: query.length > 0,
  })
}
