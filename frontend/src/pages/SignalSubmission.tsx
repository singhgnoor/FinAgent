import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Send, TrendingUp, FileText, Upload, CheckCircle2, XCircle, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { PipelineVisualizer } from "@/components/shared/PipelineVisualizer"
import { ConfidenceGauge } from "@/components/shared/ConfidenceGauge"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { usePriceTickMutation, useNewsMutation, useDocumentMutation } from "@/hooks/use-signals"
import { toast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import type { PipelineResponse } from "@/types/api"

const priceTickSchema = z.object({
  asset: z.string().min(1, "Required"),
  open: z.coerce.number().positive(),
  high: z.coerce.number().positive(),
  low: z.coerce.number().positive(),
  close: z.coerce.number().positive(),
  volume: z.coerce.number().positive(),
})

const newsSchema = z.object({
  asset: z.string().min(1, "Required"),
  headline: z.string().min(1, "Required"),
  summary: z.string().optional(),
  full_text: z.string().optional(),
})

const documentSchema = z.object({
  asset: z.string().optional(),
  doc_type: z.string().min(1, "Required"),
})

type PriceTickForm = z.infer<typeof priceTickSchema>
type NewsForm = z.infer<typeof newsSchema>
type DocumentForm = z.infer<typeof documentSchema>

export default function SignalSubmission() {
  const [tab, setTab] = useState<string>("price")
  const [result, setResult] = useState<PipelineResponse | null>(null)
  const [file, setFile] = useState<File | null>(null)

  const priceMutation = usePriceTickMutation()
  const newsMutation = useNewsMutation()
  const documentMutation = useDocumentMutation()

  const priceForm = useForm<PriceTickForm>({ resolver: zodResolver(priceTickSchema) })
  const newsForm = useForm<NewsForm>({ resolver: zodResolver(newsSchema) })
  const docForm = useForm<DocumentForm>({ resolver: zodResolver(documentSchema) })

  async function onPriceTick(data: PriceTickForm) {
    try {
      const res = await priceMutation.mutateAsync(data)
      setResult(res)
      toast({ title: "Signal processed", variant: "default" })
    } catch (e: any) {
      toast({ title: "Submission failed", description: e.message, variant: "destructive" })
    }
  }

  async function onNews(data: NewsForm) {
    try {
      const res = await newsMutation.mutateAsync(data)
      setResult(res)
      toast({ title: "Signal processed", variant: "default" })
    } catch (e: any) {
      toast({ title: "Submission failed", description: e.message, variant: "destructive" })
    }
  }

  async function onDocument(data: DocumentForm) {
    if (!file) {
      toast({ title: "Please select a file", variant: "destructive" })
      return
    }
    try {
      const res = await documentMutation.mutateAsync({ file, docType: data.doc_type, asset: data.asset })
      setResult(res)
      toast({ title: "Document processed", variant: "default" })
    } catch (e: any) {
      toast({ title: "Submission failed", description: e.message, variant: "destructive" })
    }
  }

  const isLoading = priceMutation.isPending || newsMutation.isPending || documentMutation.isPending
  const decision = result?.decision
  const hypothesis = result?.hypothesis
  const trace = result?.trace_log
  const passages = result?.retrieved_passages

  return (
    <div>
      <PageHeader
        title="Signal Submission"
        description="Submit financial signals for AI-powered analysis"
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3 space-y-6">
          <AnimatedCard delay={0}>
            <CardHeader>
              <CardTitle>New Signal</CardTitle>
              <CardDescription>Choose the signal type and fill in the details</CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="mb-4">
                  <TabsTrigger value="price" className="gap-2">
                    <TrendingUp className="h-4 w-4" /> Price Tick
                  </TabsTrigger>
                  <TabsTrigger value="news" className="gap-2">
                    <FileText className="h-4 w-4" /> News
                  </TabsTrigger>
                  <TabsTrigger value="document" className="gap-2">
                    <Upload className="h-4 w-4" /> Document
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="price">
                  <form onSubmit={priceForm.handleSubmit(onPriceTick)} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="p-asset">Asset</Label>
                      <Input id="p-asset" placeholder="e.g. AAPL, BTC/USD" {...priceForm.register("asset")} />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {(["open", "high", "low", "close"] as const).map((f) => (
                        <div key={f} className="space-y-2">
                          <Label className="capitalize">{f}</Label>
                          <Input type="number" step="any" {...priceForm.register(f)} />
                        </div>
                      ))}
                    </div>
                    <div className="space-y-2">
                      <Label>Volume</Label>
                      <Input type="number" step="any" {...priceForm.register("volume")} />
                    </div>
                    <Button type="submit" className="w-full" disabled={isLoading}>
                      {isLoading ? "Processing..." : "Submit Price Tick"} <Send className="h-4 w-4" />
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="news">
                  <form onSubmit={newsForm.handleSubmit(onNews)} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Asset</Label>
                      <Input placeholder="e.g. AAPL" {...newsForm.register("asset")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Headline *</Label>
                      <Input placeholder="News headline" {...newsForm.register("headline")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Summary</Label>
                      <Input placeholder="Brief summary" {...newsForm.register("summary")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Full Text</Label>
                      <Textarea rows={4} placeholder="Full article text" {...newsForm.register("full_text")} />
                    </div>
                    <Button type="submit" className="w-full" disabled={isLoading}>
                      {isLoading ? "Processing..." : "Submit News"} <Send className="h-4 w-4" />
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="document">
                  <form onSubmit={docForm.handleSubmit(onDocument)} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Asset (optional)</Label>
                      <Input placeholder="e.g. INFY" {...docForm.register("asset")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Document Type</Label>
                      <Input placeholder="e.g. filing, earnings_call" {...docForm.register("doc_type")} />
                    </div>
                    <div className="space-y-2">
                      <Label>File</Label>
                      <div
                        className={cn(
                          "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors cursor-pointer hover:border-primary/50",
                          file ? "border-primary bg-primary/5" : "border-muted-foreground/25"
                        )}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault()
                          const f = e.dataTransfer.files[0]
                          if (f) setFile(f)
                        }}
                        onClick={() => document.getElementById("file-upload")?.click()}
                      >
                        <Upload className="h-8 w-8 mb-2 text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">
                          {file ? file.name : "Drop a file or click to browse"}
                        </p>
                      </div>
                      <input
                        id="file-upload"
                        type="file"
                        accept=".pdf,application/pdf"
                        className="hidden"
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                      />
                    </div>
                    <Button type="submit" className="w-full" disabled={isLoading || !file}>
                      {isLoading ? "Processing..." : "Submit Document"} <Send className="h-4 w-4" />
                    </Button>
                  </form>
                </TabsContent>
              </Tabs>
            </CardContent>
          </AnimatedCard>
        </div>

        <div className="lg:col-span-2">
          <AnimatedCard delay={0.2} className="h-full">
            <CardHeader>
              <CardTitle>Pipeline Output</CardTitle>
              <CardDescription>Full analysis trace</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ) : result ? (
                <ScrollArea className="h-[600px] pr-4">
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium mb-2">Pipeline</h4>
                      <PipelineVisualizer trace={trace} />
                    </div>

                    <Separator />

                    <div>
                      <h4 className="text-sm font-medium mb-2">Status</h4>
                      <StatusBadge status={result.success ? "ok" : "error"} />
                    </div>

                    {hypothesis && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-2">Hypothesis</h4>
                          <Badge
                            variant="outline"
                            className={
                              hypothesis.classification === "bullish" ? "border-green-500/30 text-green-500" :
                              hypothesis.classification === "bearish" ? "border-red-500/30 text-red-500" :
                              "border-slate-500/30 text-slate-400"
                            }
                          >
                            {hypothesis.classification}
                          </Badge>
                          <p className="text-xs text-muted-foreground mt-2">{hypothesis.rationale}</p>
                        </div>
                      </>
                    )}

                    {decision && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-2">Decision</h4>
                          <div className="flex items-center gap-2 mb-2">
                            <Badge className={
                              decision.action === "BUY" ? "bg-green-500/20 text-green-500" :
                              decision.action === "SELL" ? "bg-red-500/20 text-red-500" :
                              "bg-amber-500/20 text-amber-500"
                            }>
                              {decision.action}
                            </Badge>
                            <StatusBadge status={decision.confidence_level} />
                          </div>
                          <p className="text-xs text-muted-foreground">{decision.llm_commentary}</p>
                          <div className="flex justify-center my-2">
                            <ConfidenceGauge score={decision.confidence_score} size="sm" />
                          </div>
                          {decision.risk_flags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {decision.risk_flags.map((f) => (
                                <Badge key={f} variant="outline" className="text-[10px]">{f}</Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </>
                    )}

                    {passages && passages.length > 0 && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-2">Retrieved Passages</h4>
                          {passages.map((p, i) => (
                            <div key={i} className="rounded border p-2 mb-2 text-xs">
                              <p className="line-clamp-2">{p.text}</p>
                              <p className="text-muted-foreground mt-1">{p.source_document} · Score: {Math.round(p.similarity_score * 100)}%</p>
                            </div>
                          ))}
                        </div>
                      </>
                    )}

                    {trace && trace.length > 0 && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-2">Trace Log</h4>
                          {trace.map((t, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs mb-1">
                              {t.status === "ok" ? <CheckCircle2 className="h-3 w-3 text-green-500" /> :
                               t.status === "error" ? <XCircle className="h-3 w-3 text-red-500" /> :
                               <AlertTriangle className="h-3 w-3 text-amber-500" />}
                              <span className="font-medium">{t.agent}</span>
                              <span className="text-muted-foreground">({t.duration_ms}ms)</span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}

                    {result.errors[0] && (
                      <div className="rounded bg-destructive/10 p-2 text-xs text-destructive">
                        {result.errors[0]}
                      </div>
                    )}
                  </div>
                </ScrollArea>
              ) : (
                <div className="flex flex-col items-center justify-center h-[400px] text-muted-foreground">
                  <Send className="h-12 w-12 mb-4 opacity-30" />
                  <p className="text-sm">Submit a signal to see the output</p>
                </div>
              )}
            </CardContent>
          </AnimatedCard>
        </div>
      </div>
    </div>
  )
}
