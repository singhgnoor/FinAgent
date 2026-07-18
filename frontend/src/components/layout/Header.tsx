import { cn } from "@/lib/utils"
import { Moon, Sun, Menu } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/store/app-store"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { useSystemStatus } from "@/hooks/use-system"
import { useLocation } from "react-router-dom"

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/live-analysis": "Live Analysis",
  "/signal-submission": "Signal Submission",
  "/knowledge-base": "Knowledge Base",
  "/decision-history": "Decision History",
  "/trace-viewer": "Trace Viewer",
  "/settings": "Settings",
  "/system-health": "System Health",
  "/about": "About",
}

export function Header() {
  const { theme, toggleTheme, toggleSidebar, sidebarOpen } = useAppStore()
  const { data: status } = useSystemStatus()
  const location = useLocation()

  return (
    <header className={cn("sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 sm:px-6", sidebarOpen ? "ml-64" : "ml-16")}>
      {!sidebarOpen && (
        <Button variant="ghost" size="icon" onClick={toggleSidebar}>
          <Menu className="h-5 w-5" />
        </Button>
      )}

      <div className="flex-1">
        <h2 className="text-sm font-semibold">{pageTitles[location.pathname] || "FinAgent"}</h2>
      </div>

      <div className="flex items-center gap-2">
        {status && (
          <StatusBadge
            status={status.pipeline_available ? "Available" : "Not Available"}
          />
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
      </div>
    </header>
  )
}
