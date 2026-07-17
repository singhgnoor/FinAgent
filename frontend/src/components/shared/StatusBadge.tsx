import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: string
  className?: string
}

const statusColorMap: Record<string, string> = {
  ok: "text-green-500 border-green-500/30 bg-green-500/10",
  error: "text-red-500 border-red-500/30 bg-red-500/10",
  fallback: "text-amber-500 border-amber-500/30 bg-amber-500/10",
  ready: "text-green-500 border-green-500/30 bg-green-500/10",
  processing: "text-blue-500 border-blue-500/30 bg-blue-500/10",
  completed: "text-green-500 border-green-500/30 bg-green-500/10",
  failed: "text-red-500 border-red-500/30 bg-red-500/10",
  idle: "text-slate-400 border-slate-500/30 bg-slate-500/10",
  not_ready: "text-amber-500 border-amber-500/30 bg-amber-500/10",
  configured: "text-green-500 border-green-500/30 bg-green-500/10",
  not_configured: "text-red-500 border-red-500/30 bg-red-500/10",
  available: "text-green-500 border-green-500/30 bg-green-500/10",
  not_available: "text-red-500 border-red-500/30 bg-red-500/10",
  "not configured": "text-red-500 border-red-500/30 bg-red-500/10",
  "not ready": "text-amber-500 border-amber-500/30 bg-amber-500/10",
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const colorClass = statusColorMap[status.toLowerCase()] || "text-slate-400 border-slate-500/30 bg-slate-500/10"

  return (
    <Badge variant="outline" className={cn(colorClass, className)}>
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </Badge>
  )
}
