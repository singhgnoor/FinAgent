import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle, AlertTriangle, ArrowRight, Loader2 } from "lucide-react"
import type { TraceEvent } from "@/types/api"
import { AGENT_LABELS } from "@/constants/theme"

interface PipelineVisualizerProps {
  trace?: TraceEvent[]
  className?: string
}

const statusIcon = {
  ok: <CheckCircle2 className="h-5 w-5 text-green-500" />,
  error: <XCircle className="h-5 w-5 text-red-500" />,
  fallback: <AlertTriangle className="h-5 w-5 text-amber-500" />,
  processing: <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />,
}

const agents = ["ingestion_agent", "retrieval_agent", "analysis_agent", "decision_agent"] as const

export function PipelineVisualizer({ trace, className }: PipelineVisualizerProps) {
  const traceMap = new Map(trace?.map((t) => [t.agent, t]) || [])

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {agents.map((agent, i) => {
        const t = traceMap.get(agent)
        const status = t?.status || "idle"
        const icon = statusIcon[status as keyof typeof statusIcon] || (
          <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30" />
        )

        return (
          <div key={agent} className="flex items-center gap-2">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                  status === "ok" && "border-green-500 bg-green-500/10",
                  status === "error" && "border-red-500 bg-red-500/10",
                  status === "fallback" && "border-amber-500 bg-amber-500/10",
                  status === "processing" && "border-blue-500 bg-blue-500/10",
                  status === "idle" && "border-muted-foreground/20 bg-muted/30"
                )}
                title={t ? `${AGENT_LABELS[agent]}: ${t.duration_ms}ms` : AGENT_LABELS[agent]}
              >
                {icon}
              </div>
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                {AGENT_LABELS[agent]}
              </span>
            </div>
            {i < agents.length - 1 && (
              <ArrowRight className="h-4 w-4 text-muted-foreground/40 -mt-5" />
            )}
          </div>
        )
      })}
    </div>
  )
}
