import { Info, TrendingUp, Cpu, Database, GitBranch, Brain, FileText, Shield } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { PageHeader } from "@/components/shared/PageHeader"
import { AnimatedCard } from "@/components/shared/AnimatedCard"

const techStack = [
  { name: "React 19", role: "Frontend Framework", icon: Brain },
  { name: "TypeScript", role: "Type Safety", icon: Shield },
  { name: "FastAPI", role: "Backend API", icon: Cpu },
  { name: "ChromaDB", role: "Vector Store", icon: Database },
  { name: "LangChain", role: "LLM Orchestration", icon: GitBranch },
  { name: "OpenAI", role: "Language Model", icon: Brain },
  { name: "Tailwind CSS", role: "Styling", icon: FileText },
  { name: "Recharts", role: "Data Visualization", icon: TrendingUp },
]

const pipelineStages = [
  { name: "Ingestion Agent", description: "Receives and normalizes raw financial signals (price ticks, news, documents) into structured events" },
  { name: "Retrieval Agent", description: "Searches the vector knowledge base for relevant context and historical patterns" },
  { name: "Analysis Agent", description: "Uses LLMs to analyze the signal with retrieved context, forming a hypothesis" },
  { name: "Decision Agent", description: "Generates a final trading decision with confidence scoring, risk flags, and alerts" },
]

export default function About() {
  return (
    <div>
      <PageHeader
        title="About FinAgent"
        description="AI-powered financial signal analysis and trading decision system"
      />

      <div className="space-y-6 max-w-4xl">
        <AnimatedCard delay={0}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-5 w-5" />
              Project Overview
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-relaxed text-muted-foreground">
              FinAgent is an intelligent financial analysis platform that processes raw market signals
              through a multi-agent pipeline to generate actionable trading decisions. The system
              ingests price ticks, news articles, and documents, retrieves relevant context from a
              vector knowledge base, analyzes signals using LLMs, and produces structured decisions
              with confidence scoring and risk assessment.
            </p>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="rounded-md bg-muted/50 p-3">
                <p className="font-medium">Signal Processing</p>
                <p className="text-muted-foreground">Real-time price tick and news analysis</p>
              </div>
              <div className="rounded-md bg-muted/50 p-3">
                <p className="font-medium">RAG Pipeline</p>
                <p className="text-muted-foreground">Retrieval-augmented generation with vector search</p>
              </div>
              <div className="rounded-md bg-muted/50 p-3">
                <p className="font-medium">Decision Engine</p>
                <p className="text-muted-foreground">BUY/SELL/HOLD/WATCH with confidence scoring</p>
              </div>
              <div className="rounded-md bg-muted/50 p-3">
                <p className="font-medium">Alert System</p>
                <p className="text-muted-foreground">Risk flag detection and threshold-based alerts</p>
              </div>
            </div>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.1}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Architecture
            </CardTitle>
            <CardDescription>Four-stage agent pipeline</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {pipelineStages.map((stage, i) => (
                <div key={i} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-bold">
                      {i + 1}
                    </div>
                    {i < pipelineStages.length - 1 && (
                      <div className="w-px flex-1 bg-border" />
                    )}
                  </div>
                  <div className="pb-4">
                    <h4 className="text-sm font-medium">{stage.name}</h4>
                    <p className="text-xs text-muted-foreground mt-1">{stage.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.2}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5" />
              Tech Stack
            </CardTitle>
            <CardDescription>Technologies powering FinAgent</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {techStack.map((tech) => (
                <div
                  key={tech.name}
                  className="flex flex-col items-center gap-2 rounded-lg border p-4 text-center"
                >
                  <tech.icon className="h-6 w-6 text-primary" />
                  <div>
                    <p className="text-sm font-medium">{tech.name}</p>
                    <p className="text-[10px] text-muted-foreground">{tech.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.3}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Version
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Frontend:</span>{" "}
                <Badge variant="outline">1.0.0</Badge>
              </div>
              <div>
                <span className="text-muted-foreground">API:</span>{" "}
                <Badge variant="outline">v1</Badge>
              </div>
              <div>
                <span className="text-muted-foreground">Environment:</span>{" "}
                <Badge variant="outline">Development</Badge>
              </div>
            </div>
          </CardContent>
        </AnimatedCard>

        <AnimatedCard delay={0.4}>
          <CardHeader><CardTitle>Development Team</CardTitle><CardDescription>The people building FinAgent</CardDescription></CardHeader>
          <CardContent><div className="flex flex-wrap gap-2">{["Gurnoor Singh", "Parv Singla", "Anubhav"].map((name) => <Badge key={name} variant="outline" className="px-3 py-1">{name}</Badge>)}</div></CardContent>
        </AnimatedCard>
      </div>
    </div>
  )
}
