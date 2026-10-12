"use client";

import { Skeleton } from "@/components/ui/skeleton";

export type ActivityItem = {
  id: string;
  kind: "drill" | "scam" | "family" | "other";
  title: string;
  detail?: string;
  when?: string;
};

const KIND_COLOR: Record<ActivityItem["kind"], string> = {
  drill: "bg-emerald-500",
  scam: "bg-red-500",
  family: "bg-amber-500",
  other: "bg-sky-500",
};

export function RecentActivity({
  items,
  loading,
}: {
  items: ActivityItem[];
  loading?: boolean;
}) {
  return (
    <div className="glass-panel p-5 md:p-6">
      <h3 className="text-lg font-semibold">Recent Activity</h3>
      {loading ? (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">No activity yet.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <li key={item.id} className="flex gap-3 text-sm">
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${KIND_COLOR[item.kind]}`}
                aria-hidden
              />
              <div>
                <p className="font-medium">{item.title}</p>
                {item.detail ? (
                  <p className="text-muted-foreground">{item.detail}</p>
                ) : null}
                {item.when ? (
                  <p className="text-xs text-muted-foreground/80">{item.when}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
