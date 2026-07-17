import { HeartPulse, Cpu, Database, GitBranch, Clock, Activity } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { useSystemHealth, useSystemStatus } from "@/hooks/use-system"

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)
  return parts.join(" ") || "< 1m"
}

export default function SystemHealth() {
  const { data: health, isLoading: healthLoading } = useSystemHealth()
  const { data: status, isLoading: statusLoading } = useSystemStatus()

  return (
    <div>
      <PageHeader
        title="System Health"
        description="Monitor the health and status of all FinAgent services"
      />

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-6">
        <AnimatedCard delay={0} className="p-4">
          <div className="flex items-center gap-3">
            <Cpu className="h-8 w-8 text-primary" />
            <div>
              <p className="text-sm text-muted-foreground">LLM</p>
              {statusLoading ? <Skeleton className="h-5 w-16" /> : <StatusBadge status={status?.llm_configured ? "Configured" : "Not Configured"} />}
            </div>
          </div>
        </AnimatedCard>
        <AnimatedCard delay={0.1} className="p-4">
          <div className="flex items-center gap-3">
            <Database className="h-8 w-8 text-blue-500" />
            <div>
              <p className="text-sm text-muted-foreground">Vector Store</p>
              {statusLoading ? <Skeleton className="h-5 w-16" /> : <StatusBadge status={status?.vector_store_ready ? "Ready" : "Not Ready"} />}
            </div>
          </div>
        </AnimatedCard>
        <AnimatedCard delay={0.2} className="p-4">
          <div className="flex items-center gap-3">
            <GitBranch className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-sm text-muted-foreground">Pipeline</p>
              {statusLoading ? <Skeleton className="h-5 w-16" /> : <StatusBadge status={status?.pipeline_available ? "Available" : "Not Available"} />}
            </div>
          </div>
        </AnimatedCard>
        <AnimatedCard delay={0.3} className="p-4">
          <div className="flex items-center gap-3">
            <Clock className="h-8 w-8 text-green-500" />
            <div>
              <p className="text-sm text-muted-foreground">Uptime</p>
              {statusLoading ? <Skeleton className="h-5 w-20" /> : <p className="text-lg font-bold">{status ? formatUptime(status.uptime_seconds) : "N/A"}</p>}
            </div>
          </div>
        </AnimatedCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AnimatedCard delay={0.4}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HeartPulse className="h-5 w-5" />
              Service Health
            </CardTitle>
            <CardDescription>Per-service health check results</CardDescription>
          </CardHeader>
          <CardContent>
            {healthLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : health ? (
              <div className="space-y-3">
                {Object.entries(health.services).map(([service, ok]) => (
                  <div
                    key={service}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`h-2.5 w-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
                      <span className="text-sm font-medium capitalize">
                        {service.replace(/_/g, " ")}
                      </span>
                    </div>
                    <Badge variant={ok ? "default" : "destructive"} className="text-xs">
                      {ok ? "Healthy" : "Unhealthy"}
                    </Badge>
                  </div>
                ))}
                {Object.keys(health.services).length === 0 && (
                  <p className="text-sm text-muted-foreground">No services reported</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Health data unavailable</p>
            )}
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.5}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Configuration Summary
            </CardTitle>
            <CardDescription>System configuration details</CardDescription>
          </CardHeader>
          <CardContent>
            {statusLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            ) : status ? (
              <div className="space-y-4">
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">LLM</h4>
                  <div className="rounded-md bg-muted/50 p-3 space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Model</span>
                      <span className="font-mono text-xs">{status.llm_model}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Status</span>
                      <StatusBadge status={status.llm_configured ? "Configured" : "Not Configured"} />
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Vector Store</h4>
                  <div className="rounded-md bg-muted/50 p-3 space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Status</span>
                      <StatusBadge status={status.vector_store_ready ? "Ready" : "Not Ready"} />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Documents</span>
                      <span>{status.document_count}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Embedding Model</span>
                      <span className="font-mono text-xs">{status.embedding_model}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Pipeline</h4>
                  <div className="rounded-md bg-muted/50 p-3 space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Status</span>
                      <StatusBadge status={status.pipeline_available ? "Available" : "Not Available"} />
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Configuration data unavailable</p>
            )}
          </CardContent>
        </AnimatedCard>

        {health && (
          <AnimatedCard delay={0.6} className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Detailed Checks</CardTitle>
              <CardDescription>Individual health check results</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md bg-muted/50 p-4">
                <pre className="text-xs font-mono whitespace-pre-wrap">
                  {JSON.stringify(health.checks, null, 2)}
                </pre>
              </div>
              <div className="mt-4 text-xs text-muted-foreground">
                Last updated: {new Date(health.timestamp).toLocaleString()} | Version: {health.version}
              </div>
            </CardContent>
          </AnimatedCard>
        )}
      </div>
    </div>
  )
}
