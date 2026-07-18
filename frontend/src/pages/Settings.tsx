import { useEffect, useState } from "react"
import { Moon, Save, Settings2, Sun } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"
import { useAppStore } from "@/store/app-store"
import { getConfig, saveConfig } from "@/services/settings"
import { toast } from "@/components/ui/use-toast"
import type { EditableConfig } from "@/types/api"

const labels: Record<string, string> = {
  DEFAULT_ALERT_THRESHOLD: "Confidence alert threshold (%)", LLM_PROVIDER: "LLM provider", LLM_MODEL_NAME: "LLM model", LLM_TEMPERATURE: "LLM temperature", TOP_K_DEFAULT: "Retrieval top-k", FINAL_TOP_K: "Final passages", EMBEDDING_MODEL_NAME: "Embedding model", DENSE_TOP_K: "Dense retrieval candidates", SPARSE_TOP_K: "Sparse retrieval candidates", CONFIDENCE_THRESHOLD: "Retrieval confidence threshold",
}

export default function Settings() {
  const { theme, setTheme } = useAppStore()
  const [values, setValues] = useState<EditableConfig>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  useEffect(() => { getConfig().then((data) => setValues(data.values)).catch((e) => toast({ title: "Could not load configuration", description: e.message, variant: "destructive" })).finally(() => setLoading(false)) }, [])
  const update = (key: string, value: string) => setValues((current) => ({ ...current, [key]: typeof current[key] === "number" ? Number(value) : value }))
  async function save() { setSaving(true); try { const response = await saveConfig(values); setValues(response.values); toast({ title: "Settings saved", description: "Changes apply to subsequent requests now and persist in config.py." }) } catch (e: any) { toast({ title: "Save failed", description: e.response?.data?.detail || e.message, variant: "destructive" }) } finally { setSaving(false) } }
  return <div><PageHeader title="Settings" description="Edit runtime configuration; saved values persist to the backend config file." />
    <div className="max-w-3xl space-y-6"><AnimatedCard delay={0}><CardHeader><CardTitle>Appearance</CardTitle><CardDescription>Theme state is shared across all navigation in this open session.</CardDescription></CardHeader><CardContent className="flex gap-3"><Button variant={theme === "light" ? "default" : "outline"} onClick={() => setTheme("light")}><Sun /> Light</Button><Button variant={theme === "dark" ? "default" : "outline"} onClick={() => setTheme("dark")}><Moon /> Dark</Button></CardContent></AnimatedCard>
      <AnimatedCard delay={0.1}><CardHeader><CardTitle className="flex items-center gap-2"><Settings2 /> System configuration</CardTitle><CardDescription>Only safe, user-relevant values are exposed. Credentials and paths remain server-only.</CardDescription></CardHeader><CardContent>{loading ? <p className="text-muted-foreground">Loading configuration…</p> : <div className="space-y-4">{Object.entries(values).map(([key, value]) => <div key={key} className="grid gap-2 sm:grid-cols-2 sm:items-center"><Label htmlFor={key}>{labels[key] || key}</Label><Input id={key} type={typeof value === "number" ? "number" : "text"} step={key.includes("TEMPERATURE") || key.includes("CONFIDENCE") ? "0.01" : "1"} value={value} onChange={(e) => update(key, e.target.value)} /></div>)}<Button onClick={save} disabled={saving} className="mt-2"><Save /> {saving ? "Saving…" : "Save configuration"}</Button></div>}</CardContent></AnimatedCard>
    </div></div>
}
