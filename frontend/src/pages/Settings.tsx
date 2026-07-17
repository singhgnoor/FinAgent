import { useState } from "react"
import { Settings as SettingsIcon, Sun, Moon, Sliders, Cpu, Database, BookOpen } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { useAppStore } from "@/store/app-store"
import { useSystemStatus } from "@/hooks/use-system"

export default function Settings() {
  const { theme, setTheme } = useAppStore()
  const { data: status, isLoading } = useSystemStatus()
  const [alertThreshold, setAlertThreshold] = useState(70)

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Configure FinAgent preferences and view system configuration"
      />

      <div className="space-y-6 max-w-2xl">
        <AnimatedCard delay={0}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sun className="h-5 w-5" />
              Appearance
            </CardTitle>
            <CardDescription>Toggle between light and dark mode</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Button
                variant={theme === "light" ? "default" : "outline"}
                size="sm"
                onClick={() => setTheme("light")}
                className="gap-2"
              >
                <Sun className="h-4 w-4" /> Light
              </Button>
              <Button
                variant={theme === "dark" ? "default" : "outline"}
                size="sm"
                onClick={() => setTheme("dark")}
                className="gap-2"
              >
                <Moon className="h-4 w-4" /> Dark
              </Button>
            </div>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.1}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sliders className="h-5 w-5" />
              Alert Threshold
            </CardTitle>
            <CardDescription>
              Decisions with confidence below this threshold will trigger alerts
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <Slider
                value={[alertThreshold]}
                onValueChange={([v]) => setAlertThreshold(v)}
                max={100}
                step={1}
                className="flex-1"
              />
              <span className="text-sm font-mono w-10 text-right">{alertThreshold}%</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Currently set to {alertThreshold}%. {alertThreshold <= 30 ? "Most decisions will generate alerts." :
                alertThreshold >= 80 ? "Only very low confidence decisions will alert." :
                "Moderate alert sensitivity."}
            </p>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.2}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5" />
              LLM Configuration
            </CardTitle>
            <CardDescription>Language model settings (read-only)</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-32" />
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Status</span>
                  <StatusBadge status={status?.llm_configured ? "Configured" : "Not Configured"} />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Model</span>
                  <span className="font-mono text-xs">{status?.llm_model || "N/A"}</span>
                </div>
              </div>
            )}
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.3}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              RAG Settings
            </CardTitle>
            <CardDescription>Vector store configuration (read-only)</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-32" />
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Vector Store</span>
                  <StatusBadge status={status?.vector_store_ready ? "Ready" : "Not Ready"} />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Embedding Model</span>
                  <span className="font-mono text-xs">{status?.embedding_model || "N/A"}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Documents</span>
                  <span>{status?.document_count ?? 0}</span>
                </div>
              </div>
            )}
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.4}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Configuration Reference
            </CardTitle>
            <CardDescription>System configuration summary</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              <div className="rounded-md bg-muted/50 p-4">
                <pre className="text-xs font-mono whitespace-pre-wrap">
                  {JSON.stringify({
                    llm: { configured: status?.llm_configured, model: status?.llm_model },
                    vector_store: { ready: status?.vector_store_ready, documents: status?.document_count, embedding: status?.embedding_model },
                    pipeline: { available: status?.pipeline_available },
                  }, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </AnimatedCard>
      </div>
    </div>
  )
}
