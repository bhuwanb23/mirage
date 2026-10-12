"use client";

import { useCallback, useEffect, useState } from "react";
import { Flame, Network, Shield, Users } from "lucide-react";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { RecentActivity, type ActivityItem } from "@/components/dashboard/recent-activity";
import { ResilienceChart } from "@/components/dashboard/resilience-chart";
import { ScamWeatherWidget } from "@/components/dashboard/scam-weather-widget";
import { StatCard } from "@/components/dashboard/stat-card";
import {
  api,
  type DrillScoreOut,
  type FamilyStatus,
  type GraphStats,
  type MapCity,
} from "@/lib/api";
import { getDisplayName, getFamilyGroupId, getUserId } from "@/lib/auth";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [score, setScore] = useState<DrillScoreOut | null>(null);
  const [scoreErr, setScoreErr] = useState<string | null>(null);
  const [family, setFamily] = useState<FamilyStatus | null>(null);
  const [familyErr, setFamilyErr] = useState<string | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [statsErr, setStatsErr] = useState<string | null>(null);
  const [cities, setCities] = useState<MapCity[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [name, setName] = useState("friend");

  const load = useCallback(async () => {
    const userId = getUserId();
    setName(getDisplayName());
    setLoading(true);

    const [scoreRes, histRes, analyzeRes, familyRes, heatRes, graphRes] =
      await Promise.allSettled([
        api.drillScore(userId),
        api.drillHistory(userId, 5),
        api.analyzeRecent(5),
        api.familyStatus(userId, getFamilyGroupId()),
        api.mapHeatmap(),
        api.graphStats(),
      ]);

    if (scoreRes.status === "fulfilled") {
      setScore(scoreRes.value);
      setScoreErr(null);
    } else {
      setScore(null);
      setScoreErr("unavailable");
    }

    if (familyRes.status === "fulfilled") {
      setFamily(familyRes.value);
      setFamilyErr(null);
    } else {
      setFamily(null);
      setFamilyErr("unavailable");
    }

    if (graphRes.status === "fulfilled") {
      setStats(graphRes.value);
      setStatsErr(null);
    } else {
      setStats(null);
      setStatsErr("unavailable");
    }

    if (heatRes.status === "fulfilled") {
      setCities(heatRes.value.cities ?? []);
    } else {
      setCities([]);
    }

    const items: ActivityItem[] = [];
    if (histRes.status === "fulfilled") {
      for (const d of histRes.value.items) {
        items.push({
          id: `drill-${d.drill_id ?? d.created_at}-${d.scam_type}`,
          kind: "drill",
          title: `Drill: ${d.scam_type}`,
          detail: `Score ${d.score_after}${d.score_change ? ` (${d.score_change >= 0 ? "+" : ""}${d.score_change})` : ""}`,
          when: d.created_at ? new Date(d.created_at).toLocaleString() : undefined,
        });
      }
    }
    if (analyzeRes.status === "fulfilled") {
      for (const a of analyzeRes.value.items) {
        items.push({
          id: `analyze-${a.created_at}-${a.scam_type}`,
          kind: a.type === "scam_detected" ? "scam" : "other",
          title: a.summary || a.scam_type,
          detail: `${Math.round((a.confidence || 0) * 100)}% · ${a.input_type}`,
          when: a.created_at ? new Date(a.created_at).toLocaleString() : undefined,
        });
      }
    }
    items.sort((a, b) => (b.when || "").localeCompare(a.when || ""));
    setActivity(items.slice(0, 5));
    setLoading(false);
  }, []);

  // Initial data load. `load` is stable (empty deps), so this runs once.
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot dashboard prefetch on mount
  }, []);

  return (
    <div className="page-shell space-y-8">
      <header className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-widest text-emerald-400/90">
          Your protection hub
        </p>
        <h1 className="page-title">Dashboard</h1>
        <p className="max-w-xl text-muted-foreground">
          Welcome back, <span className="font-medium text-foreground">{name}</span>.
          Track drills, family safety, and live scam intelligence in one place.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Resilience Score"
          value={score?.current_score ?? 0}
          suffix="/100"
          change={score?.change}
          changeLabel="from last drill"
          icon={<Shield className="h-8 w-8" />}
          href="/drill"
          loading={loading}
          error={scoreErr}
          onRetry={() => void load()}
        />
        <StatCard
          title="Drills completed"
          value={score?.drills_completed ?? 0}
          icon={<Flame className="h-8 w-8" />}
          href="/drill"
          loading={loading}
          error={scoreErr}
          onRetry={() => void load()}
        />
        <StatCard
          title="Scams in graph"
          value={stats?.scam_reports ?? 0}
          icon={<Network className="h-8 w-8" />}
          href="/graph"
          loading={loading}
          error={statsErr}
          onRetry={() => void load()}
        />
        <StatCard
          title="Family protected"
          value={family?.member_count ?? 0}
          changeLabel={family?.handshake_ready ? "handshake ready" : undefined}
          icon={<Users className="h-8 w-8" />}
          href="/family"
          loading={loading}
          error={familyErr}
          onRetry={() => void load()}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ResilienceChart
          data={score?.history ?? []}
          loading={loading}
          empty={!loading && (score?.drills_completed ?? 0) === 0}
        />
        <ScamWeatherWidget cities={cities} loading={loading} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RecentActivity items={activity} loading={loading} />
        <QuickActions />
      </div>
    </div>
  );
}
