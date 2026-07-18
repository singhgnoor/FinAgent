import { useEffect, useState, useRef } from "react"
import { Database, Upload, Search, RefreshCw, FileText, X, Inbox, Trash2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { EmptyState } from "@/components/shared/EmptyState"
import { ErrorState } from "@/components/shared/ErrorState"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { useKnowledgeBaseStatus, useUploadDocuments, useReindex, useKBSearch } from "@/hooks/use-knowledge-base"
import { toast } from "@/components/ui/use-toast"
import { getIngestionStatus } from "@/services/knowledge-base"
import type { IngestionStatus } from "@/types/api"

export default function KnowledgeBase() {
  const { data: kbStatus, isLoading, isError, refetch } = useKnowledgeBaseStatus()
  const uploadMutation = useUploadDocuments()
  const reindexMutation = useReindex()
  const [searchDraft, setSearchDraft] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const { data: searchResults, isError: searchFailed, error: searchError, isFetching: searchLoading } = useKBSearch(searchQuery)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [ingestionId, setIngestionId] = useState<string | null>(null)
  const [ingestion, setIngestion] = useState<IngestionStatus | null>(null)

  useEffect(() => {
    if (!ingestionId) return
    let cancelled = false
    const poll = async () => {
      try {
        const status = await getIngestionStatus(ingestionId)
        if (cancelled) return
        setIngestion(status)
        if (status.status === "completed") { toast({ title: "Ingestion complete" }); refetch(); return }
        if (status.status === "failed") { toast({ title: "Ingestion failed", description: status.error, variant: "destructive" }); return }
        window.setTimeout(poll, 800)
      } catch (error: any) { if (!cancelled) toast({ title: "Could not read ingestion status", description: error.message, variant: "destructive" }) }
    }
    poll()
    return () => { cancelled = true }
  }, [ingestionId, refetch])

  async function handleUpload(files: FileList | null) {
    if (!files?.length) return
    try {
      const queued = await uploadMutation.mutateAsync(Array.from(files))
      setIngestionId(queued.ingestion_id)
      setIngestion({ id: queued.ingestion_id, status: "queued", stage: "queued", completed_chunks: 0, total_chunks: 0 })
      toast({ title: "Upload queued", description: "The live ingestion status will update below." })
    } catch (e: any) {
      toast({ title: "Upload failed", description: e.message, variant: "destructive" })
    }
  }

  async function handleReindex() {
    try {
      await reindexMutation.mutateAsync()
      toast({ title: "Reindex complete", variant: "success" })
      refetch()
    } catch (e: any) {
      toast({ title: "Reindex failed", description: e.message, variant: "destructive" })
    }
  }

  return (
    <div>
      <PageHeader
        title="Knowledge Base"
        description="Manage the vector store documents and search"
        action={
          <Button variant="outline" size="sm" onClick={handleReindex} disabled={reindexMutation.isPending}>
            <RefreshCw className={`h-4 w-4 mr-1 ${reindexMutation.isPending ? "animate-spin" : ""}`} />
            Reindex
          </Button>
        }
      />

      <div className="grid gap-6 md:grid-cols-3 mb-6">
        <AnimatedCard delay={0} className="p-4">
          <div className="flex items-center gap-3">
            <Database className="h-8 w-8 text-primary" />
            <div>
              <p className="text-sm text-muted-foreground">Documents</p>
              {isLoading ? <Skeleton className="h-8 w-12" /> : <p className="text-2xl font-bold">{kbStatus?.total_documents ?? 0}</p>}
            </div>
          </div>
        </AnimatedCard>
        <AnimatedCard delay={0.1} className="p-4">
          <div className="flex items-center gap-3">
            <FileText className="h-8 w-8 text-blue-500" />
            <div>
              <p className="text-sm text-muted-foreground">Chunks</p>
              {isLoading ? <Skeleton className="h-8 w-12" /> : <p className="text-2xl font-bold">{kbStatus?.total_chunks ?? 0}</p>}
            </div>
          </div>
        </AnimatedCard>
        <AnimatedCard delay={0.2} className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
              <div className={`h-3 w-3 rounded-full ${kbStatus?.index_ready ? 'bg-green-500' : 'bg-amber-500'}`} />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Index Status</p>
              {isLoading ? <Skeleton className="h-8 w-20" /> : <StatusBadge status={kbStatus?.index_ready ? 'Ready' : 'Not Ready'} />}
            </div>
          </div>
        </AnimatedCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <AnimatedCard delay={0.3}>
            <CardHeader>
              <CardTitle>Upload Documents</CardTitle>
              <CardDescription>Add PDF reports to the knowledge base</CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors cursor-pointer hover:border-primary/50"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  handleUpload(e.dataTransfer.files)
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-10 w-10 mb-3 text-muted-foreground" />
                <p className="text-sm font-medium mb-1">Drop files here or click to browse</p>
                <p className="text-xs text-muted-foreground">Supports PDF files</p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => handleUpload(e.target.files)}
              />
              {(uploadMutation.isPending || ingestion) && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs text-muted-foreground">{uploadMutation.isPending ? "Uploading…" : ingestion?.stage}</p>
                  <Progress value={ingestion?.total_chunks ? Math.round((ingestion.completed_chunks / ingestion.total_chunks) * 100) : ingestion?.status === "completed" ? 100 : 0} className="h-1" />
                  {ingestion?.total_chunks ? <p className="text-xs text-muted-foreground">{ingestion.completed_chunks}/{ingestion.total_chunks} chunks embedded</p> : null}
                </div>
              )}
            </CardContent>
          </AnimatedCard>

          <AnimatedCard delay={0.4}>
            <CardHeader>
              <CardTitle>Search</CardTitle>
              <CardDescription>Search through document contents</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); setSearchQuery(searchDraft.trim()) }}>
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search..."
                    className="pl-8"
                    value={searchDraft}
                    onChange={(e) => setSearchDraft(e.target.value)}
                  />
                </div>
                <Button type="submit" disabled={!searchDraft.trim() || searchLoading}><Search className="mr-1" /> Search</Button>
                {searchDraft && (
                  <Button type="button" variant="ghost" size="icon" onClick={() => { setSearchDraft(""); setSearchQuery("") }}>
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </form>
              {searchLoading && <p className="text-xs text-muted-foreground">Searching the knowledge base…</p>}
              {searchFailed && <p className="text-xs text-destructive">{(searchError as Error)?.message || "Search failed"}</p>}
              {searchQuery && searchResults?.results && (
                <ScrollArea className="h-[200px]">
                  <div className="space-y-2">
                    {searchResults.results.map((r, i) => (
                      <div key={i} className="rounded border p-2 text-xs">
                        <p className="line-clamp-2">{r.text}</p>
                        <div className="flex justify-between mt-1 text-muted-foreground">
                          <span className="truncate max-w-[200px]">{r.source_document}</span>
                          <span>{Math.round(r.similarity_score * 100)}%</span>
                        </div>
                        <pre className="mt-2 overflow-x-auto rounded bg-muted/60 p-2 text-[10px]">Metadata: {JSON.stringify(r.metadata, null, 2)}</pre>
                      </div>
                    ))}
                    {searchResults.results.length === 0 && (
                      <p className="text-xs text-muted-foreground text-center py-4">No results found</p>
                    )}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </AnimatedCard>
        </div>

        <AnimatedCard delay={0.5}>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
            <CardDescription>Uploaded documents in the knowledge base</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : isError ? (
              <ErrorState title="Failed to load" message="Could not reach the backend API" onRetry={() => refetch()} />
            ) : kbStatus && kbStatus.total_documents > 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <FileText className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm font-medium">{kbStatus.total_documents} document(s) indexed</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Embedding model: {kbStatus.embedding_model}
                </p>
                <p className="text-xs text-muted-foreground">
                  Dimensions: {kbStatus.dimensions}
                </p>
              </div>
            ) : (
              <EmptyState
                icon={<Inbox className="h-12 w-12" />}
                title="No documents"
                description="Upload files to populate the knowledge base."
              />
            )}
          </CardContent>
        </AnimatedCard>
      </div>
    </div>
  )
}
