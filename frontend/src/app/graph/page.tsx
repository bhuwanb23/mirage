"use client";

import { useMemo } from "react";
import {
  Radar,
  Globe,
  Phone,
  IndianRupee,
  Users,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { GRAPH_STATS, SCAM_TYPES } from "@/lib/constants";

const CAMPAIGNS = [
  {
    name: "Fake FedEx parcel",
    nodes: 412,
    types: ["Phone", "UPI ID", "Domain"],
    active: true,
    lastSeen: "12m ago",
  },
  {
    name: "RBI KYC update",
    nodes: 308,
    types: ["Phone", "WhatsApp"],
    active: true,
    lastSeen: "48m ago",
  },
  {
    name: "Parcel customs fee",
    nodes: 191,
    types: ["Phone", "Domain"],
    active: false,
    lastSeen: "6h ago",
  },
  {
    name: "Job offer — data entry",
    nodes: 154,
    types: ["Phone", "Email"],
    active: false,
    lastSeen: "1d ago",
  },
];

export default function GraphPage() {
  const byType = useMemo(
    () =>
      SCAM_TYPES.map((t, i) => ({
        label: t.label.split(" ")[0],
        reports: [184, 142, 96, 78, 64, 51, 43, 37][i] ?? 30,
      })),
    [],
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Radar className="h-6 w-6 text-emerald-400" aria-hidden />
          <h1 className="text-2xl font-bold tracking-tight">Scam Graph</h1>
          <Badge variant="outline" className="font-mono text-[10px]">
            Phase 5
          </Badge>
        </div>
        <Badge variant="secondary" className="font-mono">
          Neo4j Aura
        </Badge>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        The honeypot consumes scam bait and lights up shared infrastructure. This is
        a weather map of active fraud.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Phones", value: GRAPH_STATS[0].value, icon: Phone },
          { label: "UPI IDs", value: GRAPH_STATS[1].value, icon: IndianRupee },
          { label: "Domains", value: GRAPH_STATS[2].value, icon: Globe },
          { label: "Campaigns", value: GRAPH_STATS[3].value, icon: Users },
        ].map((s) => (
          <Card key={s.label} className="border-border/60">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{s.label}</span>
                <s.icon className="h-4 w-4 text-emerald-400" aria-hidden />
              </div>
              <div className="mt-1 text-3xl font-bold font-mono">
                {s.value.toLocaleString()}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle>Reports by scam type</CardTitle>
            <CardDescription>Placeholder counts for Phase 5 seeding.</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byType} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: "#09090b",
                    border: "1px solid #27272a",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="reports" fill="#10b981" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle>Active campaigns</CardTitle>
            <CardDescription>Clusters sharing phone / UPI / domain nodes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {CAMPAIGNS.map((c) => (
              <div
                key={c.name}
                className="flex items-start justify-between gap-3 rounded-md border border-border/60 p-3"
              >
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    {c.name}
                    <Badge
                      variant={c.active ? "default" : "secondary"}
                      className="text-[10px]"
                    >
                      {c.active ? "active" : "dormant"}
                    </Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.types.map((t) => (
                      <Badge key={t} variant="outline" className="text-[10px] font-mono">
                        {t}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-lg">{c.nodes}</div>
                  <div className="text-xs text-muted-foreground">{c.lastSeen}</div>
                </div>
              </div>
            ))}
            <Separator />
            <p className="text-xs text-muted-foreground">
              Graph queries run against Neo4j with the constraints in{" "}
              <code className="font-mono">backend/db/002_neo4j_constraints.cypher</code>.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
