import { motion } from "framer-motion"
import { Activity, Database, AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { PipelineVisualizer } from "@/components/shared/PipelineVisualizer"
import { ConfidenceGauge } from "@/components/shared/ConfidenceGauge"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { ErrorState } from "@/components/shared/ErrorState"
import { useDecisions } from "@/hooks/use-decisions"
import { useSystemHealth, useSystemStatus } from "@/hooks/use-system"
import { useKnowledgeBaseStatus } from "@/hooks/use-knowledge-base"
import { useRecentSignals } from "@/hooks/use-signals"
import { useLatestPipelineJob } from "@/hooks/use-signals"
import { useNavigate } from "react-router-dom"

const actionIcon = {
  BUY: <TrendingUp className="h-4 w-4 text-green-500" />,
  SELL: <TrendingDown className="h-4 w-4 text-red-500" />,
  HOLD: <Minus className="h-4 w-4 text-amber-500" />,
  WATCH: <Activity className="h-4 w-4 text-amber-500" />,
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: decisionsData, isLoading: decisionsLoading, isError: decisionsError, refetch: refetchDecisions } = useDecisions({ page_size: 5 })
  const { data: health, isLoading: healthLoading, isError: healthError, refetch: refetchHealth } = useSystemHealth()
  const { data: status, isLoading: statusLoading } = useSystemStatus()
  const { data: kbStatus, isLoading: kbLoading } = useKnowledgeBaseStatus()
  const { data: signalsData } = useRecentSignals()
  const { data: activeJob } = useLatestPipelineJob()

  const latestDecision = decisionsData?.items?.[0]
  const totalDecisions = decisionsData?.total ?? 0
  const alertCount = decisionsData?.items?.filter((d) => d.alert_triggered).length ?? 0

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Real-time overview of the FinAgent system"
      />

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-6">
        <AnimatedCard delay={0} className="p-4">
          <div className="flex items-center gap-3">
            <Activity className="h-8 w-8 text-primary" />
            <div>
              <p className="text-sm text-muted-foreground">Total Decisions</p>
              {decisionsLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <p className="text-2xl font-bold">{totalDecisions}</p>
              )}
            </div>
          </div>
        </AnimatedCard>

        <AnimatedCard delay={0.1} className="p-4 cursor-pointer" onClick={() => navigate("/decision-history?alerted=true")} title="View decisions that triggered alerts">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-sm text-muted-foreground">Alerts Triggered</p>
              {decisionsLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <p className="text-2xl font-bold">{alertCount}</p>
              )}
            </div>
          </div>
        </AnimatedCard>

        <AnimatedCard delay={0.2} className="p-4">
          <div className="flex items-center gap-3">
            <Database className="h-8 w-8 text-blue-500" />
            <div>
              <p className="text-sm text-muted-foreground">KB Documents</p>
              {kbLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <p className="text-2xl font-bold">{kbStatus?.total_documents ?? 0}</p>
              )}
            </div>
          </div>
        </AnimatedCard>

        <AnimatedCard delay={0.3} className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
              <div className={`h-3 w-3 rounded-full ${status?.pipeline_available ? 'bg-green-500' : 'bg-red-500'}`} />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">System Status</p>
              {statusLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <p className="text-2xl font-bold">{status?.pipeline_available ? 'Online' : 'Offline'}</p>
              )}
            </div>
          </div>
        </AnimatedCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 mb-6">
        <AnimatedCard delay={0.4}>
          <CardHeader>
            <CardTitle className="text-lg">Latest Decision</CardTitle>
          </CardHeader>
          <CardContent>
            {decisionsLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-20 w-full" />
              </div>
            ) : decisionsError ? (
              <ErrorState title="Failed to load decisions" message="Could not reach the backend API" onRetry={() => refetchDecisions()} />
            ) : latestDecision ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-sm">
                      {latestDecision.asset}
                    </Badge>
                    <Badge
                      className={
                        latestDecision.action === "BUY" ? "bg-green-500/20 text-green-500 border-green-500/30" :
                        latestDecision.action === "SELL" ? "bg-red-500/20 text-red-500 border-red-500/30" :
                        "bg-amber-500/20 text-amber-500 border-amber-500/30"
                      }
                      variant="outline"
                    >
                      {actionIcon[latestDecision.action]}
                      <span className="ml-1">{latestDecision.action}</span>
                    </Badge>
                  </div>
                  <StatusBadge status={latestDecision.confidence_level} />
                </div>
                <p className="text-sm text-muted-foreground">{latestDecision.llm_commentary || latestDecision.evidence_bullets[0]}</p>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Risks: {latestDecision.risk_flags.length}</span>
                  <span>{new Date(latestDecision.created_at).toLocaleString()}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No decisions yet</p>
            )}
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.5}>
          <CardHeader>
            <CardTitle className="text-lg">Agent Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            {decisionsLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
              </div>
            ) : (
              <PipelineVisualizer trace={activeJob?.result?.trace_log || latestDecision?.trace_log} className="justify-center py-4" />
            )}
            {!activeJob?.result?.trace_log && !latestDecision?.trace_log && (
              <p className="text-xs text-muted-foreground text-center mt-2">The dashboard updates automatically while a submitted signal is processed.</p>
            )}
          </CardContent>
        </AnimatedCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 mb-6">
        <AnimatedCard delay={0.6} className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Recent Decisions</CardTitle>
          </CardHeader>
          <CardContent>
            {decisionsLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : decisionsError ? (
              <ErrorState title="Failed to load decisions" message="Could not reach the backend API" onRetry={() => refetchDecisions()} />
            ) : decisionsData?.items?.length ? (
              <div className="space-y-2">
                {decisionsData.items.map((d) => (
                  <div
                    key={d.artefact_id}
                    className="flex items-center justify-between rounded-lg border p-3 text-sm cursor-pointer hover:border-primary/50 hover:bg-accent/40"
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/decision-history?decision=${encodeURIComponent(d.artefact_id)}`)}
                    onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") navigate(`/decision-history?decision=${encodeURIComponent(d.artefact_id)}`) }}
                  >
                    <div className="flex items-center gap-3">
                      {actionIcon[d.action]}
                      <div>
                        <span className="font-medium">{d.asset}</span>
                        <span className="text-muted-foreground ml-2">
                          {d.normalized_event?.event_type || "signal"}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge
                        variant="outline"
                        className={
                          d.confidence_score >= 70 ? "border-green-500/30 text-green-500" :
                          d.confidence_score >= 40 ? "border-amber-500/30 text-amber-500" :
                          "border-red-500/30 text-red-500"
                        }
                      >
                        <span title="Model confidence in this hypothesis, 0–100">{Math.round(d.confidence_score)}%</span>
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(d.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No recent decisions</p>
            )}
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.7}>
          <CardHeader>
            <CardTitle className="text-lg">System Health</CardTitle>
          </CardHeader>
          <CardContent>
            {healthLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </div>
            ) : healthError ? (
              <ErrorState title="Failed to load health" message="Could not reach the backend API" onRetry={() => refetchHealth()} />
            ) : health ? (
              <div className="space-y-3">
                {Object.entries(health.services).map(([service, ok]) => (
                  <div key={service} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground capitalize">
                      {service.replace(/_/g, ' ')}
                    </span>
                    <StatusBadge status={ok ? 'ok' : 'error'} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Health data unavailable</p>
            )}
          </CardContent>
        </AnimatedCard>
      </div>

      {latestDecision && (
        <AnimatedCard delay={0.8}>
          <CardHeader>
            <CardTitle className="text-lg">Confidence Score</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center py-6">
            <ConfidenceGauge score={latestDecision.confidence_score} size="lg" />
          </CardContent>
        </AnimatedCard>
      )}

      <AnimatedCard delay={0.9} className="mt-6">
        <CardHeader><CardTitle className="text-lg">Live Signal Feed</CardTitle></CardHeader>
        <CardContent>
          {signalsData?.items?.length ? (
            <div className="space-y-2">
              {signalsData.items.map((signal) => (
                <div key={signal.event_id} className="flex justify-between gap-3 rounded-lg border p-3 text-sm">
                  <span><strong>{signal.asset || "GENERAL"}</strong> · {signal.event_type}</span>
                  <span className="text-xs text-muted-foreground">{new Date(signal.timestamp).toLocaleString()}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-muted-foreground">No signals ingested yet.</p>}
        </CardContent>
      </AnimatedCard>
    </div>
  )
}
