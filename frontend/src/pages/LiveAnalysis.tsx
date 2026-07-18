import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Activity, Download, FileText, Send, TrendingUp } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { PipelineVisualizer } from "@/components/shared/PipelineVisualizer"
import { ConfidenceGauge } from "@/components/shared/ConfidenceGauge"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { toast } from "@/components/ui/use-toast"
import { getMarketData, getPipelineJob, processNews, processPriceTick, startNewsJob, startPriceTickJob } from "@/services/signals"
import type { NewsRequest, PipelineJob, PipelineResponse, PriceTickRequest, RetrievedPassage } from "@/types/api"

const priceTickSchema = z.object({ asset: z.string().min(1, "Ticker is required"), open: z.coerce.number().positive(), high: z.coerce.number().positive(), low: z.coerce.number().positive(), close: z.coerce.number().positive(), volume: z.coerce.number().positive() })
const newsSchema = z.object({ asset: z.string().min(1, "Asset is required"), headline: z.string().min(1, "Headline is required"), summary: z.string().optional(), full_text: z.string().optional() })
type PriceTickForm = z.infer<typeof priceTickSchema>
type NewsForm = z.infer<typeof newsSchema>

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export default function LiveAnalysis() {
  const [tab, setTab] = useState<"price" | "news">("price")
  const [job, setJob] = useState<PipelineJob | null>(null)
  const [loadingMarketData, setLoadingMarketData] = useState(false)
  const priceForm = useForm<PriceTickForm>({ resolver: zodResolver(priceTickSchema), defaultValues: { asset: "HDFCBANK.NS" } })
  const newsForm = useForm<NewsForm>({ resolver: zodResolver(newsSchema) })

  async function pollJob(jobId: string) {
    for (;;) {
      const next = await getPipelineJob(jobId)
      setJob(next)
      if (next.status === "completed") { toast({ title: "Analysis complete" }); return }
      if (next.status === "failed") throw new Error(next.error || "Pipeline failed")
      await wait(700)
    }
  }

  async function fetchTicker() {
    const ticker = priceForm.getValues("asset").trim()
    if (!ticker) return
    setLoadingMarketData(true)
    try {
      const quote = await getMarketData(ticker)
      priceForm.reset({ asset: quote.asset || ticker.toUpperCase(), open: quote.open, high: quote.high, low: quote.low, close: quote.close, volume: quote.volume })
      toast({ title: "Recent OHLCV loaded", description: `${quote.asset || ticker.toUpperCase()} via ${quote.source}` })
    } catch (error: any) {
      toast({ title: "Live data unavailable", description: error?.response?.data?.detail || "Enter OHLCV values manually.", variant: "destructive" })
    } finally { setLoadingMarketData(false) }
  }

  async function submitPrice(data: PriceTickForm) {
    try { const started = await startPriceTickJob(data as PriceTickRequest); setJob({ ...started, signal_id: started.signal_id || "", status: "queued", stage: "queued" }); await pollJob(started.job_id) }
    catch (error: any) {
      // Keep the original synchronous API path as a compatibility fallback
      // for a backend that has not been restarted with job endpoints yet.
      if (error?.response?.status === 404) {
        try { setJob(fromDirectResult(await processPriceTick(data as PriceTickRequest))); toast({ title: "Analysis complete" }); return } catch (fallbackError: any) { error = fallbackError }
      }
      toast({ title: "Analysis failed", description: error.message, variant: "destructive" })
    }
  }
  async function submitNews(data: NewsForm) {
    try { const started = await startNewsJob(data as NewsRequest); setJob({ ...started, signal_id: started.signal_id || "", status: "queued", stage: "queued" }); await pollJob(started.job_id) }
    catch (error: any) {
      if (error?.response?.status === 404) {
        try { setJob(fromDirectResult(await processNews(data as NewsRequest))); toast({ title: "Analysis complete" }); return } catch (fallbackError: any) { error = fallbackError }
      }
      toast({ title: "Analysis failed", description: error.message, variant: "destructive" })
    }
  }

  const result = job?.result
  const busy = job?.status === "queued" || job?.status === "running"
  return <div>
    <PageHeader title="Live Analysis" description="Fetch a supported ticker or enter a fallback signal; outputs appear as each agent finishes." />
    <div className="grid gap-6 lg:grid-cols-2">
      <AnimatedCard delay={0}><CardHeader><CardTitle>Signal Input</CardTitle><CardDescription>yFinance fills known tickers; manual OHLCV remains available for offline or unsupported symbols.</CardDescription></CardHeader><CardContent>
        <Tabs value={tab} onValueChange={(value) => setTab(value as "price" | "news")}><TabsList className="mb-4"><TabsTrigger value="price"><TrendingUp /> Price tick</TabsTrigger><TabsTrigger value="news"><FileText /> News</TabsTrigger></TabsList>
          <TabsContent value="price"><form onSubmit={priceForm.handleSubmit(submitPrice)} className="space-y-4"><div className="space-y-2"><Label htmlFor="asset">Ticker</Label><div className="flex gap-2"><Input id="asset" placeholder="HDFCBANK.NS" {...priceForm.register("asset")} /><Button type="button" variant="outline" onClick={fetchTicker} disabled={loadingMarketData || busy}><Download /> {loadingMarketData ? "Fetching" : "Fetch OHLCV"}</Button></div><p className="text-xs text-muted-foreground">Try HDFCBANK.NS, TCS.NS, or INFY.NS. Fetch failures unlock the manual fallback below.</p></div><div className="grid grid-cols-2 gap-3">{(["open", "high", "low", "close"] as const).map((field) => <div key={field} className="space-y-1"><Label htmlFor={field} className="capitalize">{field}</Label><Input id={field} type="number" step="any" {...priceForm.register(field)} /></div>)}</div><div className="space-y-1"><Label htmlFor="volume">Volume</Label><Input id="volume" type="number" step="any" {...priceForm.register("volume")} /></div><Button type="submit" className="w-full" disabled={busy}>{busy ? "Pipeline running…" : "Analyze signal"}<Send /></Button></form></TabsContent>
          <TabsContent value="news"><form onSubmit={newsForm.handleSubmit(submitNews)} className="space-y-4"><div className="space-y-1"><Label>Asset</Label><Input placeholder="HDFC" {...newsForm.register("asset")} /></div><div className="space-y-1"><Label>Headline</Label><Input placeholder="News headline" {...newsForm.register("headline")} /></div><div className="space-y-1"><Label>Summary</Label><Input placeholder="Optional summary" {...newsForm.register("summary")} /></div><div className="space-y-1"><Label>Full text</Label><Textarea rows={4} placeholder="Optional article text" {...newsForm.register("full_text")} /></div><Button type="submit" className="w-full" disabled={busy}>{busy ? "Pipeline running…" : "Analyze news"}<Send /></Button></form></TabsContent>
        </Tabs></CardContent></AnimatedCard>
      <AnimatedCard delay={0.1}><CardHeader><CardTitle>Progressive agent output</CardTitle><CardDescription>{job ? `${job.status}: ${job.stage}` : "Start an analysis to reveal each output sequentially."}</CardDescription></CardHeader><CardContent>{job ? <ScrollArea className="h-[590px] pr-3"><div className="space-y-5"><PipelineVisualizer trace={result?.trace_log} /><AgentSection title="1. Ingestion — normalized event" value={result?.normalized_event} active={job.stage === "ingestion_agent"} /><AgentSection title="2. Retrieval — ranked passages" value={result?.retrieved_passages} active={job.stage === "retrieval_agent"} /><AgentSection title="3. Analysis — hypothesis" value={result?.hypothesis} active={job.stage === "analysis_agent"} />{result?.decision && <div className="space-y-2"><Separator /><h4 className="font-medium">4. Decision — final artefact</h4><div className="flex items-center gap-2"><Badge className={`semantic-${result.decision.action.toLowerCase()}`}>{result.decision.action}</Badge><StatusBadge status={result.decision.confidence_level} /></div><p className="text-sm text-muted-foreground">{result.decision.llm_commentary}</p><ConfidenceGauge score={result.decision.confidence_score} size="sm" /></div>}{job.error && <p className="rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{job.error}</p>}</div></ScrollArea> : <div className="flex h-[300px] flex-col items-center justify-center text-muted-foreground"><Activity className="mb-3 h-10 w-10" />The backend state will appear here after each agent completes.</div>}</CardContent></AnimatedCard>
    </div></div>
}

function AgentSection({ title, value, active }: { title: string; value: unknown; active: boolean }) {
  const passages = Array.isArray(value) ? value as RetrievedPassage[] : null
  return <div className="space-y-2"><Separator /><h4 className="font-medium">{title} {active && <span className="text-xs text-primary">processing…</span>}</h4>{passages ? <div className="space-y-2">{passages.map((passage) => <div key={passage.passage_id} className="rounded-md border bg-muted/30 p-3 text-xs"><p>{passage.text}</p><p className="mt-2 text-muted-foreground">Source: {passage.source_document} · {passage.section_reference || "Unspecified section"}</p><pre className="mt-2 overflow-x-auto rounded bg-background/60 p-2 text-[11px]">Metadata: {JSON.stringify(passage.metadata, null, 2)}</pre></div>)}</div> : value ? <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs whitespace-pre-wrap">{JSON.stringify(value, null, 2)}</pre> : <p className="text-sm text-muted-foreground">Waiting for this agent.</p>}</div>
}

function fromDirectResult(result: PipelineResponse): PipelineJob {
  return { job_id: `direct-${result.signal_id}`, signal_id: result.signal_id, status: result.success ? "completed" : "failed", stage: result.success ? "completed" : "failed", result, error: result.errors[0] }
}
