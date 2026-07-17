import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { ROUTES } from "@/constants/routes"
import { useAppStore } from "@/store/app-store"
import {
  LayoutDashboard,
  Activity,
  Send,
  Database,
  History,
  GitBranch,
  Settings,
  HeartPulse,
  Info,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, path: ROUTES.DASHBOARD },
  { label: "Live Analysis", icon: Activity, path: ROUTES.LIVE_ANALYSIS },
  { label: "Signal Submission", icon: Send, path: ROUTES.SIGNAL_SUBMISSION },
  { label: "Knowledge Base", icon: Database, path: ROUTES.KNOWLEDGE_BASE },
  { label: "Decision History", icon: History, path: ROUTES.DECISION_HISTORY },
  { label: "Trace Viewer", icon: GitBranch, path: ROUTES.TRACE_VIEWER },
  { label: "Settings", icon: Settings, path: ROUTES.SETTINGS },
  { label: "System Health", icon: HeartPulse, path: ROUTES.SYSTEM_HEALTH },
  { label: "About", icon: Info, path: ROUTES.ABOUT },
]

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useAppStore()

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r bg-card transition-all duration-300",
        sidebarOpen ? "w-64" : "w-16"
      )}
    >
      <div className="flex h-14 items-center border-b px-4 gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <TrendingUp className="h-5 w-5 text-primary-foreground" />
        </div>
        {sidebarOpen && (
          <span className="font-semibold text-lg whitespace-nowrap">FinAgent</span>
        )}
      </div>

      <ScrollArea className="flex-1 py-2">
        <nav className="flex flex-col gap-1 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )
              }
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
      </ScrollArea>

      <div className="border-t p-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="w-full justify-center"
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      </div>
    </aside>
  )
}
