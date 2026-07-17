import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'

interface AppState {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  setTheme: (theme: 'light' | 'dark') => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

const AppContext = createContext<AppState | null>(null)

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('finagent-theme')
    if (stored === 'light' || stored === 'dark') return stored
  }
  return 'dark'
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev)
  }, [])

  const persistTheme = useCallback((t: 'light' | 'dark') => {
    localStorage.setItem('finagent-theme', t)
    setTheme(t)
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <AppContext.Provider value={{ theme, sidebarOpen, setTheme: persistTheme, toggleSidebar, setSidebarOpen }}>
      {children}
    </AppContext.Provider>
  )
}

export function useAppStore(): AppState {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useAppStore must be used within AppProvider')
  return ctx
}
