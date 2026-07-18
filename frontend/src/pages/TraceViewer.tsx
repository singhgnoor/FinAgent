import { useState } from "react"
import {
  GitBranch, CheckCircle2, XCircle, AlertTriangle, ArrowRight,
  Clock, Terminal, ChevronDown, ChevronRight
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { EmptyState } from "@/components/shared/EmptyState"
import { useDecisions } from "@/hooks/use-decisions"
import { useDecision } from "@/hooks/use-decisions"
import { cn } from "@/lib/utils"
import { AGENT_LABELS } from "@/constants/theme"
import type { TraceEvent, AgentName } from "@/types/api"

const agentOrder: AgentName[] = [
  "ingestion_agent", "retrieval_agent", "analysis_agent", "decision_agent"
]

const statusIcon = {
  ok: <CheckCircle2 className="h-5 w-5 text-green-500" />,
  error: <XCircle className="h-5 w-5 text-red-500" />,
  fallback: <AlertTriangle className="h-5 w-5 text-amber-500" />,
}

const statusColor = {
  ok: "border-green-500/30 bg-green-500/5",
  error: "border-red-500/30 bg-red-500/5",
  fallback: "border-amber-500/30 bg-amber-500/5",
}

export default function TraceViewer() {
  const { data: decisionsData } = useDecisions({ page_size: 50 })
  const [selectedId, setSelectedId] = useState<string>("")
  const { data: decision, isLoading } = useDecision(selectedId || undefined)

  const trace: TraceEvent[] = decision?.trace_log || []

  return (
    <div>
      <PageHeader
        title="Trace Viewer"
        description="Inspect the pipeline trace for any decision"
      />

      <div className="mb-6">
        <AnimatedCard delay={0}>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Select Decision</CardTitle>
            <CardDescription>Choose a decision to view its trace</CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedId} onValueChange={setSelectedId}>
              <SelectTrigger className="w-full max-w-md">
                <SelectValue placeholder="Select a decision..." />
              </SelectTrigger>
              <SelectContent>
                {decisionsData?.items?.map((d: any) => (
                  <SelectItem key={d.artefact_id || d.decision_id} value={d.artefact_id || d.decision_id}>
                    {d.asset} - {d.action} ({new Date(d.created_at || d.timestamp).toLocaleString()})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </AnimatedCard>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : trace.length > 0 ? (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-2">
            {agentOrder.map((agent, i) => {
              const t = trace.find((e) => e.agent === agent)
              return (
                <div key={agent} className="flex items-center gap-2 flex-1">
                  <div
                    className={cn(
                      "flex-1 rounded-lg border p-3 text-center transition-colors",
                      t ? statusColor[t.status as keyof typeof statusColor] || "border-muted" : "border-muted/30 opacity-50"
                    )}
                  >
                    <div className="flex justify-center mb-1">
                      {t ? (statusIcon[t.status as keyof typeof statusIcon] || <Terminal className="h-5 w-5" />) : <Terminal className="h-5 w-5 text-muted-foreground" />}
                    </div>
                    <p className="text-xs font-medium">{AGENT_LABELS[agent]}</p>
                    {t && (
                      <p className="text-[10px] text-muted-foreground mt-1">{t.duration_ms}ms</p>
                    )}
                  </div>
                  {i < agentOrder.length - 1 && (
                    <ArrowRight className="h-4 w-4 text-muted-foreground/40 shrink-0" />
                  )}
                </div>
              )
            })}
          </div>

          {trace.map((event, idx) => (
            <TraceEventCard key={idx} event={event} index={idx} />
          ))}
        </div>
      ) : selectedId ? (
        <EmptyState
          title="No trace data"
          description="This decision has no trace information."
        />
      ) : (
        <EmptyState
          icon={<GitBranch className="h-12 w-12" />}
          title="Select a decision"
          description="Choose a decision above to view its pipeline trace."
        />
      )}
    </div>
  )
}

function TraceEventCard({ event, index }: { event: TraceEvent; index: number }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <AnimatedCard delay={index * 0.1}>
      <CardHeader className="pb-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {statusIcon[event.status as keyof typeof statusIcon] || <Terminal className="h-5 w-5" />}
            <div>
              <CardTitle className="text-base">{AGENT_LABELS[event.agent]}</CardTitle>
              <CardDescription>{event.agent}</CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {event.duration_ms}ms
            </div>
            <StatusBadge status={event.status} />
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </div>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent>
          <div className="space-y-4">
            <div>
              <h5 className="text-xs font-medium text-muted-foreground mb-1">Input</h5>
              <div className="rounded-md bg-muted/50 p-3">
                <pre className="text-xs whitespace-pre-wrap font-mono">
                  {event.input_summary || JSON.stringify(event.raw_input, null, 2) || "N/A"}
                </pre>
              </div>
            </div>
            <div>
              <h5 className="text-xs font-medium text-muted-foreground mb-1">Output</h5>
              <div className="rounded-md bg-muted/50 p-3">
                <pre className="text-xs whitespace-pre-wrap font-mono">
                  {event.output_summary || JSON.stringify(event.raw_output, null, 2) || "N/A"}
                </pre>
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </AnimatedCard>
  )
}
