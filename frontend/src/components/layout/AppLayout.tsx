import { Sidebar } from "./Sidebar"
import { Header } from "./Header"
import { MainContent } from "./MainContent"

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <MainContent>{children}</MainContent>
      </div>
    </div>
  )
}
