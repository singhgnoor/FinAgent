import { cn } from "@/lib/utils"

interface ConfidenceGaugeProps {
  score: number
  size?: "sm" | "md" | "lg"
  showLabel?: boolean
}

const sizeMap = {
  sm: { width: 80, stroke: 6 },
  md: { width: 120, stroke: 8 },
  lg: { width: 160, stroke: 10 },
}

function getColor(score: number) {
  if (score >= 70) return "#22c55e"
  if (score >= 40) return "#f59e0b"
  return "#ef4444"
}

export function ConfidenceGauge({ score, size = "md", showLabel = true }: ConfidenceGaugeProps) {
  const { width, stroke } = sizeMap[size]
  const radius = (width - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.min(score, 100) / 100) * circumference
  const color = getColor(score)

  return (
    <div className="flex flex-col items-center gap-1" title="Model confidence in this hypothesis, 0–100">
      <svg width={width} height={width} className="-rotate-90">
        <circle
          cx={width / 2}
          cy={width / 2}
          r={radius}
          stroke="hsl(var(--muted))"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={width / 2}
          cy={width / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      {showLabel && (
        <span className={cn("font-bold", size === "lg" ? "text-2xl" : size === "md" ? "text-lg" : "text-sm")} style={{ color }}>
          {Math.round(score)}%
        </span>
      )}
    </div>
  )
}
