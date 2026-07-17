import React, { useState } from "react"
import { motion } from "framer-motion"
import {
  History, ChevronDown, ChevronUp, Download, Search,
  TrendingUp, TrendingDown, Minus, Activity, AlertTriangle
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { EmptyState } from "@/components/shared/EmptyState"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { useDecisions } from "@/hooks/use-decisions"

const actionIcon: Record<string, React.ReactNode> = {
  BUY: <TrendingUp className="h-4 w-4 text-green-500" />,
  SELL: <TrendingDown className="h-4 w-4 text-red-500" />,
  HOLD: <Minus className="h-4 w-4 text-amber-500" />,
  WATCH: <Activity className="h-4 w-4 text-amber-500" />,
}

export default function DecisionHistory() {
  const [page, setPage] = useState(1)
  const [searchAsset, setSearchAsset] = useState("")
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  const { data, isLoading } = useDecisions({ page, page_size: 10 })

  const filtered = data?.items?.filter((d: any) =>
    !searchAsset || (d.asset || "").toLowerCase().includes(searchAsset.toLowerCase())
  )

  function toggleRow(id: string) {
    setExpandedRow((prev) => (prev === id ? null : id))
  }

  function handleExport() {
    if (!data?.items) return
    const headers = ["Timestamp", "Asset", "Action", "Confidence", "Level", "Alert", "Commentary"]
    const rows = data.items.map((d: any) =>
      [
        d.created_at || d.timestamp || "",
        d.asset,
        d.action,
        d.confidence_score ?? d.confidence ?? "",
        d.confidence_level || "",
        d.alert_triggered ?? d.alert ?? "",
        `"${((d.llm_commentary || d.commentary || "")).replace(/"/g, '""')}"`,
      ].join(",")
    )
    const blob = new Blob([headers.join(","), ...rows].join("\n"), { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "decisions.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        title="Decision History"
        description="Browse all decisions made by the FinAgent pipeline"
        action={
          <Button variant="outline" size="sm" onClick={handleExport} disabled={!data?.items?.length}>
            <Download className="h-4 w-4 mr-1" />
            Export CSV
          </Button>
        }
      />

      <AnimatedCard delay={0}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Decisions</CardTitle>
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Filter by asset..."
                className="pl-8"
                value={searchAsset}
                onChange={(e) => setSearchAsset(e.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : filtered && filtered.length > 0 ? (
            <div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Asset</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Level</TableHead>
                    <TableHead>Alert</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((decision: any) => {
                    const id = decision.artefact_id || decision.decision_id
                    return (
                      <React.Fragment key={id}>
                        <TableRow
                          className="cursor-pointer"
                          onClick={() => toggleRow(id)}
                        >
                          <TableCell>
                            {expandedRow === id
                              ? <ChevronUp className="h-4 w-4" />
                              : <ChevronDown className="h-4 w-4" />}
                          </TableCell>
                          <TableCell className="text-xs">
                            {new Date(decision.created_at || decision.timestamp).toLocaleString()}
                          </TableCell>
                          <TableCell className="font-medium">{decision.asset}</TableCell>
                          <TableCell>
                            <Badge
                              className={
                                decision.action === "BUY" ? "bg-green-500/20 text-green-500" :
                                decision.action === "SELL" ? "bg-red-500/20 text-red-500" :
                                "bg-amber-500/20 text-amber-500"
                              }
                            >
                              {actionIcon[decision.action]}
                              <span className="ml-1">{decision.action}</span>
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <span
                              className={
                                (decision.confidence_score ?? decision.confidence ?? 0) >= 70 ? "text-green-500" :
                                (decision.confidence_score ?? decision.confidence ?? 0) >= 40 ? "text-amber-500" :
                                "text-red-500"
                              }
                            >
                              {Math.round(decision.confidence_score ?? decision.confidence ?? 0)}%
                            </span>
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={decision.confidence_level || "N/A"} />
                          </TableCell>
                          <TableCell>
                            {(decision.alert_triggered ?? decision.alert) ? (
                              <AlertTriangle className="h-4 w-4 text-amber-500" />
                            ) : (
                              <span className="text-muted-foreground">&mdash;</span>
                            )}
                          </TableCell>
                        </TableRow>
                        {expandedRow === id && (
                          <TableRow key={`${id}-detail`}>
                            <TableCell colSpan={7} className="bg-muted/30 p-4">
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                className="space-y-4"
                              >
                                <div className="flex gap-4 text-sm">
                                  <div>
                                    <span className="text-muted-foreground">Level:</span>{" "}
                                    <span className="font-medium">{decision.confidence_level}</span>
                                  </div>
                                  <div>
                                    <span className="text-muted-foreground">Score:</span>{" "}
                                    <span className="font-medium">{decision.confidence_score ?? decision.confidence ?? "N/A"}/100</span>
                                  </div>
                                </div>
                                {(decision.llm_commentary || decision.commentary) && (
                                  <div>
                                    <h5 className="text-sm font-medium mb-2">Commentary</h5>
                                    <p className="text-sm text-muted-foreground">{decision.llm_commentary || decision.commentary}</p>
                                  </div>
                                )}
                                {decision.risk_flags && decision.risk_flags.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-medium mb-2">Risk Flags</h5>
                                    <div className="flex flex-wrap gap-1">
                                      {decision.risk_flags.map((f: string) => (
                                        <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {decision.evidence_bullets && decision.evidence_bullets.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-medium mb-2">Evidence</h5>
                                    <ScrollArea className="h-[120px]">
                                      <div className="space-y-2">
                                        {decision.evidence_bullets.map((bullet: string, i: number) => (
                                          <div key={i} className="rounded border p-2 text-xs">
                                            {bullet}
                                          </div>
                                        ))}
                                      </div>
                                    </ScrollArea>
                                  </div>
                                )}
                              </motion.div>
                            </TableCell>
                          </TableRow>
                        )}
                      </React.Fragment>
                    )
                  })}
                </TableBody>
              </Table>

              {data && data.total_pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {data.total_pages} ({data.total} total)
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= data.total_pages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <EmptyState
              title="No decisions found"
              description={searchAsset ? "Try a different search term." : "Submit a signal to generate decisions."}
            />
          )}
        </CardContent>
      </AnimatedCard>
    </div>
  )
}
