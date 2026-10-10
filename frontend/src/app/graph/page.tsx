"use client";

import { useEffect, useState } from "react";
import { Globe, IndianRupee, Phone, Radar, Users, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import ScamGraph from "@/components/hunter/ScamGraph";
import ScamWeatherMap from "@/components/hunter/ScamWeatherMap";
import HoneypotChat from "@/components/hunter/HoneypotChat";
import ReportGenerator from "@/components/hunter/ReportGenerator";
import { api, GraphStats } from "@/lib/api";

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card className="border-border/60">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">{label}</span>
          <Icon className="h-4 w-4 text-emerald-400" aria-hidden />
        </div>
        <div className="mt-1 font-mono text-3xl font-bold" data-testid={`stat-${label}`}>
          {value.toLocaleString()}
        </div>
      </CardContent>
    </Card>
  );
}

export default function GraphPage() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [honeypotSessionId, setHoneypotSessionId] = useState("");

  useEffect(() => {
    api
      .graphStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, [honeypotSessionId]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Radar className="h-6 w-6 text-emerald-400" aria-hidden />
          <h1 className="text-2xl font-bold tracking-tight">Scammer Hunter</h1>
          <Badge variant="outline" className="font-mono text-[10px]">
            Phase 5
          </Badge>
        </div>
        <Badge variant="secondary" className="font-mono">
          graph backend: {stats?.backend ?? "…"}
        </Badge>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        The honeypot consumes scam bait and lights up shared infrastructure —
        phones, UPI IDs and domains merge into one graph, and connected rings
        surface the campaign behind them.
      </p>

      {/* Live stats (fall back to zeros while loading / offline) */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Phones" value={stats?.phone_numbers ?? 0} icon={Phone} />
        <StatCard label="UPI IDs" value={stats?.upi_ids ?? 0} icon={IndianRupee} />
        <StatCard label="Domains" value={stats?.domains ?? 0} icon={Globe} />
        <StatCard label="Accounts" value={stats?.bank_accounts ?? 0} icon={Wallet} />
        <StatCard label="Rings" value={stats?.rings ?? 0} icon={Users} />
      </div>

      <div className="mt-6">
        <ScamGraph />
      </div>

      <div className="mt-6">
        <ScamWeatherMap />
      </div>

      <div className="mt-6">
        <HoneypotChat onSessionId={setHoneypotSessionId} />
      </div>

      <div className="mt-6">
        <ReportGenerator honeypotSessionId={honeypotSessionId} />
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        Graph ingestion runs plan §5.3 Cypher against Neo4j when{" "}
        <code className="font-mono">NEO4J_URI</code> is configured, and falls
        back to an embedded MERGE-semantics store for the demo. Seed the demo
        ring with{" "}
        <code className="font-mono">uv run python tests/seed_graph.py</code>.
      </p>
    </div>
  );
}
