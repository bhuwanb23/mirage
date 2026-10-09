"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Database,
  Network,
  Cpu,
  CircleDashed,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { api, type ApiError, type HealthResponse } from "@/lib/api";
import { API_URL, GRAPH_STATS, SCORE_HISTORY } from "@/lib/constants";

type Status = "loading" | "ok" | "error";

function StatusRow({
  label,
  detail,
  state,
}: {
  label: string;
  detail: string;
  state: "ok" | "warn" | "off";
}) {
  const Icon = state === "ok" ? CheckCircle2 : state === "warn" ? CircleDashed : XCircle;
  const color =
    state === "ok" ? "text-emerald-400" : state === "warn" ? "text-amber-400" : "text-red-400";
  return (
    <div className="flex items-center justify-between gap-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${color}`} aria-hidden />
        <span>{label}</span>
      </div>
      <span className="font-mono text-xs text-muted-foreground">{detail}</span>
    </div>
  );
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((data) => {
        if (!cancelled) {
          setHealth(data);
          setStatus("ok");
        }
      })
      .catch((err: ApiError) => {
        if (!cancelled) {
          setError(err.message);
          setStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const providers = health?.providers;
  const maxScore = Math.max(...SCORE_HISTORY.map((s) => s.score), 100);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Resilience overview and backend status.
          </p>
        </div>
        <Badge variant="secondary" className="font-mono">
          {API_URL}
        </Badge>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="border-border/60 lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-400" aria-hidden />
              Resilience Score
            </CardTitle>
            <CardDescription>
              Last 7 days — placeholder history until Phase 3 ships real drills.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-end gap-3">
              <span className="text-5xl font-bold font-mono">68</span>
              <span className="pb-2 text-sm text-muted-foreground">/ 100 · +12 this week</span>
            </div>
            <Progress value={68} max={maxScore} className="h-2" />
            <div className="grid grid-cols-7 gap-2 text-center text-xs text-muted-foreground">
              {SCORE_HISTORY.map((d) => (
                <div key={d.day} className="space-y-1">
                  <div className="mx-auto flex h-20 w-full items-end rounded-sm bg-accent/50">
                    <div
                      className="w-full rounded-sm bg-emerald-500/70"
                      style={{ height: `${(d.score / maxScore) * 100}%` }}
                    />
                  </div>
                  <div>{d.day}</div>
                  <div className="font-mono text-foreground">{d.score}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-emerald-400" aria-hidden />
              Backend status
            </CardTitle>
            <CardDescription>
              Live <code className="font-mono">GET /health</code> probe.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {status === "loading" && (
              <p className="text-sm text-muted-foreground">Checking…</p>
            )}
            {status === "error" && (
              <div className="space-y-2 text-sm">
                <p className="flex items-center gap-2 text-red-400">
                  <XCircle className="h-4 w-4" aria-hidden /> Unreachable
                </p>
                <p className="text-muted-foreground">{error}</p>
                <p className="text-xs text-muted-foreground">
                  Start it with:{" "}
                  <code className="font-mono">cd backend &amp;&amp; uv run uvicorn app.main:app --port 8000</code>
                </p>
              </div>
            )}
            {status === "ok" && health && (
              <div className="divide-y divide-border/60">
                <StatusRow label="API" detail={`${health.service} v${health.version}`} state="ok" />
                <StatusRow
                  label="LLM provider"
                  detail={providers?.configured ?? "none"}
                  state={providers?.available?.length ? "ok" : "warn"}
                />
                <StatusRow
                  label="Supabase"
                  detail={providers?.supabase ? "connected" : "not configured"}
                  state={providers?.supabase ? "ok" : "warn"}
                />
                <StatusRow
                  label="Neo4j"
                  detail={providers?.neo4j ? "connected" : "not configured"}
                  state={providers?.neo4j ? "ok" : "warn"}
                />
                <StatusRow label="Environment" detail={providers?.environment ?? "?"} state="ok" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Separator className="my-6" />

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-4 w-4 text-emerald-400" aria-hidden />
            Supabase tables
          </CardTitle>
          <CardDescription>
            Six tables provisioned by <code className="font-mono">backend/db/001_init_tables.sql</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-3">
            {["users", "drills", "scam_reports", "family_groups", "family_members", "memory_secrets"].map(
              (t) => (
                <Badge key={t} variant="outline" className="justify-center font-mono">
                  {t}
                </Badge>
              ),
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-4 border-border/60">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="h-4 w-4 text-emerald-400" aria-hidden />
            Scam graph (teaser)
          </CardTitle>
          <CardDescription>
            Placeholder counts — Phase 5 fills this from the honeypot.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {GRAPH_STATS.map((s) => (
              <div key={s.label} className="rounded-md border border-border/60 p-3 text-center">
                <div className="text-2xl font-bold font-mono">{s.value.toLocaleString()}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
