"use client";

import Link from "next/link";
import type { MapCity } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

function dotColor(intensity: number): string {
  if (intensity >= 0.7) return "bg-red-500";
  if (intensity >= 0.4) return "bg-amber-500";
  return "bg-emerald-500";
}

export function ScamWeatherWidget({
  cities,
  loading,
}: {
  cities: MapCity[];
  loading?: boolean;
}) {
  const top = [...cities].sort((a, b) => b.scam_count - a.scam_count).slice(0, 3);

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">Scam Weather</h3>
        <Link
          href="/graph"
          className="text-xs text-emerald-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          View Full Map →
        </Link>
      </div>
      {loading ? (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : top.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">No heatmap data yet.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {top.map((city) => (
            <li key={city.city} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${dotColor(city.intensity)}`}
                  aria-hidden
                />
                {city.city}
              </span>
              <span className="font-mono text-muted-foreground">
                {city.scam_count} · {city.top_type}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
