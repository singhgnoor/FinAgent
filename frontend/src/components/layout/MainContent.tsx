import { cn } from "@/lib/utils"
import { useAppStore } from "@/store/app-store"

interface MainContentProps {
  children: React.ReactNode
}

export function MainContent({ children }: MainContentProps) {
  const { sidebarOpen } = useAppStore()

  return (
    <main
      className={cn(
        "flex-1 transition-all duration-300",
        sidebarOpen ? "ml-64" : "ml-16"
      )}
    >
      <div className="p-4 sm:p-6 lg:p-8">{children}</div>
    </main>
  )
}
