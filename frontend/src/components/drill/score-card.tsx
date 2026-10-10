"use client";

import { useEffect, useRef, useState } from "react";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import type { DrillRespondOut, DrillScoreOut } from "@/lib/drill-api";

/** Animated count from -> to over `durationMs` (score animation, plan 3.6). */
function useCountUp(from: number, to: number, durationMs = 900): number {
  const [value, setValue] = useState(from);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(from + (to - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [from, to, durationMs]);
  return value;
}

export function ScoreCard({ result, score }: { result: DrillRespondOut; score: DrillScoreOut | null }) {
  const display = useCountUp(result.score_before, result.score_after);
  const changeIcon =
    result.change > 0 ? TrendingUp : result.change < 0 ? TrendingDown : Minus;
  const ChangeIcon = changeIcon;
  const changeColor =
    result.change > 0 ? "text-emerald-400" : result.change < 0 ? "text-red-400" : "text-muted-foreground";

  return (
    <div className="rounded-xl border border-border/60 bg-card p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-end gap-3">
          <span className="font-mono text-5xl font-bold tabular-nums">{display}</span>
          <span className="pb-2 text-sm text-muted-foreground">/ 100</span>
          <span className={`pb-2 flex items-center gap-1 text-sm font-medium ${changeColor}`}>
            <ChangeIcon className="h-4 w-4" aria-hidden />
            {result.change > 0 ? `+${result.change}` : result.change}
          </span>
        </div>
        <Badge variant="secondary" className="font-mono">
          {result.label}
        </Badge>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        drill score {result.drill_score} ·{" "}
        {score?.drills_completed
          ? `${score.drills_completed} drill${score.drills_completed === 1 ? "" : "s"} completed`
          : "first drill"}
        {score?.best_reaction_time != null && (
          <> · best reaction {score.best_reaction_time.toFixed(1)}s</>
        )}
      </p>
    </div>
  );
}

export function ScoreChart({ score }: { score: DrillScoreOut | null }) {
  const ref = useRef<HTMLDivElement>(null);
  if (!score || score.history.length === 0) {
    return (
      <div className="rounded-xl border border-border/60 bg-card p-5">
        <h3 className="text-sm font-semibold">Resilience over time</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          No history yet — run a few drills to see your curve.
        </p>
      </div>
    );
  }
  const data = score.history.map((h) => ({
    drill: `#${h.drill_number}`,
    score: h.score,
    scam: h.scam_type,
  }));
  return (
    <div ref={ref} className="rounded-xl border border-border/60 bg-card p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Resilience over time</h3>
        <Badge variant="outline" className="font-mono text-[10px]">
          weakest: {score.weakest_scam_type ?? "—"}
        </Badge>
      </div>
      <div className="mt-3 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="drill" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fill: "#a1a1aa", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: "#09090b",
                border: "1px solid #27272a",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value) => [`${value}`, "score"]}
              labelFormatter={(label, payload) => {
                const p = payload?.[0]?.payload as { scam?: string } | undefined;
                return p?.scam ? `${label} · ${p.scam}` : String(label);
              }}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ fill: "#10b981", r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
