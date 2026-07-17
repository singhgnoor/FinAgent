import { Routes, Route } from "react-router-dom"
import { AnimatePresence } from "framer-motion"
import { AppLayout } from "@/components/layout/AppLayout"
import { ROUTES } from "@/constants/routes"

import Dashboard from "@/pages/Dashboard"
import LiveAnalysis from "@/pages/LiveAnalysis"
import SignalSubmission from "@/pages/SignalSubmission"
import KnowledgeBase from "@/pages/KnowledgeBase"
import DecisionHistory from "@/pages/DecisionHistory"
import TraceViewer from "@/pages/TraceViewer"
import Settings from "@/pages/Settings"
import SystemHealth from "@/pages/SystemHealth"
import About from "@/pages/About"

export default function App() {
  return (
    <AppLayout>
      <AnimatePresence mode="wait">
        <Routes>
          <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
          <Route path={ROUTES.LIVE_ANALYSIS} element={<LiveAnalysis />} />
          <Route path={ROUTES.SIGNAL_SUBMISSION} element={<SignalSubmission />} />
          <Route path={ROUTES.KNOWLEDGE_BASE} element={<KnowledgeBase />} />
          <Route path={ROUTES.DECISION_HISTORY} element={<DecisionHistory />} />
          <Route path={ROUTES.TRACE_VIEWER} element={<TraceViewer />} />
          <Route path={ROUTES.SETTINGS} element={<Settings />} />
          <Route path={ROUTES.SYSTEM_HEALTH} element={<SystemHealth />} />
          <Route path={ROUTES.ABOUT} element={<About />} />
        </Routes>
      </AnimatePresence>
    </AppLayout>
  )
}
