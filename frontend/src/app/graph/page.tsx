"use client";

import { useEffect, useState } from "react";
import { Globe, IndianRupee, Phone, Radar, Users, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    <div className="page-shell space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-medium uppercase tracking-widest text-emerald-400/90">
            Intelligence
          </p>
          <div className="flex items-center gap-3">
            <Radar className="h-7 w-7 text-emerald-400" aria-hidden />
            <h1 className="page-title text-3xl md:text-4xl">Scammer Hunter</h1>
          </div>
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

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Phones" value={stats?.phone_numbers ?? 0} icon={Phone} />
        <StatCard label="UPI IDs" value={stats?.upi_ids ?? 0} icon={IndianRupee} />
        <StatCard label="Domains" value={stats?.domains ?? 0} icon={Globe} />
        <StatCard label="Accounts" value={stats?.bank_accounts ?? 0} icon={Wallet} />
        <StatCard label="Rings" value={stats?.rings ?? 0} icon={Users} />
      </div>

      {/* Desktop: stacked sections. Mobile: tabs. */}
      <div className="mt-6 hidden space-y-6 lg:block">
        <ScamGraph />
        <ScamWeatherMap />
        <HoneypotChat onSessionId={setHoneypotSessionId} />
        <ReportGenerator honeypotSessionId={honeypotSessionId} />
      </div>

      <div className="mt-6 lg:hidden">
        <Tabs defaultValue="graph">
          <TabsList className="w-full justify-start overflow-x-auto">
            <TabsTrigger value="graph">Graph</TabsTrigger>
            <TabsTrigger value="map">Map</TabsTrigger>
            <TabsTrigger value="honeypot">Honeypot</TabsTrigger>
            <TabsTrigger value="report">Report</TabsTrigger>
          </TabsList>
          <TabsContent value="graph" className="mt-4">
            <ScamGraph />
          </TabsContent>
          <TabsContent value="map" className="mt-4">
            <ScamWeatherMap />
          </TabsContent>
          <TabsContent value="honeypot" className="mt-4">
            <HoneypotChat onSessionId={setHoneypotSessionId} />
          </TabsContent>
          <TabsContent value="report" className="mt-4">
            <ReportGenerator honeypotSessionId={honeypotSessionId} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
