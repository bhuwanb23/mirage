"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";

type Point = { drill_number: number; score: number; date: string; scam_type?: string };

export function ResilienceChart({
  data,
  loading,
  empty,
}: {
  data: Point[];
  loading?: boolean;
  empty?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5">
      <h3 className="text-lg font-semibold">Resilience Trend</h3>
      {loading ? (
        <Skeleton className="mt-4 h-48 w-full" />
      ) : empty || data.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">
          No drills yet — start your first one to see your trend.
        </p>
      ) : (
        <div className="mt-4 h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.slice(-10)}>
              <defs>
                <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#34d399" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="drill_number" stroke="#9ca3af" fontSize={12} />
              <YAxis domain={[0, 100]} stroke="#9ca3af" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "#111827",
                  border: "1px solid #374151",
                  borderRadius: 8,
                }}
              />
              <ReferenceLine y={50} stroke="#6b7280" strokeDasharray="4 4" label="Safe" />
              <Area
                type="monotone"
                dataKey="score"
                stroke="#34d399"
                strokeWidth={2}
                fill="url(#scoreFill)"
                isAnimationActive
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
