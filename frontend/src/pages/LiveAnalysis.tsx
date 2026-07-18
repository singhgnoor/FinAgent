import { useState } from "react"
import { motion } from "framer-motion"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Activity, TrendingUp, FileText, Send } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { PipelineVisualizer } from "@/components/shared/PipelineVisualizer"
import { ConfidenceGauge } from "@/components/shared/ConfidenceGauge"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { usePriceTickMutation, useNewsMutation } from "@/hooks/use-signals"
import { toast } from "@/components/ui/use-toast"
import type { PipelineResponse } from "@/types/api"

const priceTickSchema = z.object({
  asset: z.string().min(1, "Asset is required"),
  open: z.coerce.number().positive(),
  high: z.coerce.number().positive(),
  low: z.coerce.number().positive(),
  close: z.coerce.number().positive(),
  volume: z.coerce.number().positive(),
})

const newsSchema = z.object({
  asset: z.string().min(1, "Asset is required"),
  headline: z.string().min(1, "Headline is required"),
  summary: z.string().optional(),
  full_text: z.string().optional(),
})

type PriceTickForm = z.infer<typeof priceTickSchema>
type NewsForm = z.infer<typeof newsSchema>

export default function LiveAnalysis() {
  const [tab, setTab] = useState<"price" | "news">("price")
  const [result, setResult] = useState<PipelineResponse | null>(null)

  const priceMutation = usePriceTickMutation()
  const newsMutation = useNewsMutation()

  const priceForm = useForm<PriceTickForm>({ resolver: zodResolver(priceTickSchema) })
  const newsForm = useForm<NewsForm>({ resolver: zodResolver(newsSchema) })

  async function onPriceTick(data: PriceTickForm) {
    try {
      const res = await priceMutation.mutateAsync(data)
      setResult(res)
      toast({ title: "Analysis complete", variant: "default" })
    } catch (e: any) {
      toast({ title: "Analysis failed", description: e.message, variant: "destructive" })
    }
  }

  async function onNews(data: NewsForm) {
    try {
      const res = await newsMutation.mutateAsync(data)
      setResult(res)
      toast({ title: "Analysis complete", variant: "default" })
    } catch (e: any) {
      toast({ title: "Analysis failed", description: e.message, variant: "destructive" })
    }
  }

  const isLoading = priceMutation.isPending || newsMutation.isPending
  const decision = result?.decision
  const hypothesis = result?.hypothesis
  const trace = result?.trace_log
  const passages = result?.retrieved_passages

  return (
    <div>
      <PageHeader
        title="Live Analysis"
        description="Submit a signal and see the real-time pipeline analysis"
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <AnimatedCard delay={0}>
          <CardHeader>
            <CardTitle>Signal Input</CardTitle>
            <CardDescription>Enter market data to analyze</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={tab} onValueChange={(v) => setTab(v as "price" | "news")}>
              <TabsList className="mb-4">
                <TabsTrigger value="price" className="gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Price Tick
                </TabsTrigger>
                <TabsTrigger value="news" className="gap-2">
                  <FileText className="h-4 w-4" />
                  News
                </TabsTrigger>
              </TabsList>

              <TabsContent value="price">
                <form onSubmit={priceForm.handleSubmit(onPriceTick)} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="asset">Asset</Label>
                    <Input id="asset" placeholder="e.g. AAPL, BTC/USD" {...priceForm.register("asset")} />
                    {priceForm.formState.errors.asset && (
                      <p className="text-xs text-destructive">{priceForm.formState.errors.asset.message}</p>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {(["open", "high", "low", "close"] as const).map((field) => (
                      <div key={field} className="space-y-2">
                        <Label htmlFor={field} className="capitalize">{field}</Label>
                        <Input id={field} type="number" step="any" {...priceForm.register(field)} />
                      </div>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="volume">Volume</Label>
                    <Input id="volume" type="number" step="any" {...priceForm.register("volume")} />
                  </div>
                  <Button type="submit" className="w-full gap-2" disabled={isLoading}>
                    {isLoading ? "Analyzing..." : "Analyze"}
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="news">
                <form onSubmit={newsForm.handleSubmit(onNews)} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="news-asset">Asset</Label>
                    <Input id="news-asset" placeholder="e.g. AAPL, BTC/USD" {...newsForm.register("asset")} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="headline">Headline</Label>
                    <Input id="headline" placeholder="News headline" {...newsForm.register("headline")} />
                    {newsForm.formState.errors.headline && (
                      <p className="text-xs text-destructive">{newsForm.formState.errors.headline.message}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="summary">Summary (optional)</Label>
                    <Input id="summary" placeholder="Brief summary" {...newsForm.register("summary")} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="full_text">Full Text (optional)</Label>
                    <Textarea id="full_text" rows={4} placeholder="Full article text" {...newsForm.register("full_text")} />
                  </div>
                  <Button type="submit" className="w-full gap-2" disabled={isLoading}>
                    {isLoading ? "Analyzing..." : "Analyze"}
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.2}>
          <CardHeader>
            <CardTitle>Results</CardTitle>
            <CardDescription>Pipeline analysis output</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : result ? (
              <ScrollArea className="h-[500px] pr-4">
                <div className="space-y-6">
                  <div>
                    <h4 className="text-sm font-medium mb-2">Pipeline Status</h4>
                    <PipelineVisualizer trace={trace} />
                  </div>

                  <Separator />

                  <div>
                    <h4 className="text-sm font-medium mb-2">Hypothesis</h4>
                    {hypothesis ? (
                      <div className="space-y-2">
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
                        <p className="text-sm text-muted-foreground">{hypothesis.rationale}</p>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No hypothesis generated</p>
                    )}
                  </div>

                  <Separator />

                  <div>
                    <h4 className="text-sm font-medium mb-2">Decision</h4>
                    {decision ? (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <Badge
                            className={
                              decision.action === "BUY" ? "bg-green-500/20 text-green-500" :
                              decision.action === "SELL" ? "bg-red-500/20 text-red-500" :
                              "bg-amber-500/20 text-amber-500"
                            }
                          >
                            {decision.action}
                          </Badge>
                          <StatusBadge status={decision.confidence_level} />
                        </div>
                        <p className="text-sm">{decision.llm_commentary}</p>
                        <div className="flex justify-center py-2">
                          <ConfidenceGauge score={decision.confidence_score} size="sm" />
                        </div>
                        {decision.alert_triggered && (
                          <div className="rounded-md bg-amber-500/10 border border-amber-500/30 p-2 text-xs text-amber-500">
                            Alert: confidence exceeded the configured threshold.
                          </div>
                        )}
                        {decision.risk_flags.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {decision.risk_flags.map((flag) => (
                              <Badge key={flag} variant="outline" className="text-xs">
                                {flag}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No decision generated</p>
                    )}
                  </div>

                  {passages && passages.length > 0 && (
                    <>
                      <Separator />
                      <div>
                        <h4 className="text-sm font-medium mb-2">Retrieved Passages ({passages.length})</h4>
                        <div className="space-y-2">
                          {passages.map((p, i) => (
                            <div key={i} className="rounded-md border p-2 text-xs">
                              <p className="text-muted-foreground line-clamp-2">{p.text}</p>
                              <p className="text-xs text-muted-foreground mt-1">
                                Source: {p.source_document} | Score: {Math.round(p.similarity_score * 100)}%
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}

                  {result.errors[0] && (
                    <div className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive">
                      Error: {result.errors[0]}
                    </div>
                  )}
                </div>
              </ScrollArea>
            ) : (
              <div className="flex flex-col items-center justify-center h-[300px] text-muted-foreground">
                <Activity className="h-12 w-12 mb-4 opacity-30" />
                <p className="text-sm">Submit a signal to see results</p>
              </div>
            )}
          </CardContent>
        </AnimatedCard>
      </div>
    </div>
  )
}
