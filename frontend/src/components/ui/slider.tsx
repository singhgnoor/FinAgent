import * as React from "react"
import { cn } from "@/lib/utils"

interface SliderProps {
  value: number[]
  onValueChange: (value: number[]) => void
  min?: number
  max?: number
  step?: number
  className?: string
}

function Slider({ value, onValueChange, min = 0, max = 100, step = 1, className }: SliderProps) {
  const trackRef = React.useRef<HTMLDivElement>(null)

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!trackRef.current) return
    const rect = trackRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const newVal = Math.round((min + x * (max - min)) / step) * step
    onValueChange([Math.max(min, Math.min(max, newVal))])
  }

  const pct = ((value[0] - min) / (max - min)) * 100

  return (
    <div
      ref={trackRef}
      className={cn("relative h-2 w-full cursor-pointer rounded-full bg-primary/20", className)}
      onClick={handleClick}
    >
      <div
        className="absolute h-full rounded-full bg-primary transition-all"
        style={{ width: `${pct}%` }}
      />
      <div
        className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-primary bg-background shadow transition-all"
        style={{ left: `${pct}%`, marginLeft: "-8px" }}
      />
    </div>
  )
}

export { Slider }
