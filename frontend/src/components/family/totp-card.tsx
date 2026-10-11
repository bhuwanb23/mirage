"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

export function TotpCard({ familyGroupId }: { familyGroupId: string }) {
  const [code, setCode] = useState<string>("——————");
  const [expires, setExpires] = useState(0);
  const [intervalSec, setIntervalSec] = useState(300);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    const refresh = async () => {
      try {
        const res = await api.memoryTotp(familyGroupId);
        if (cancelled) return;
        setCode(res.code);
        setExpires(res.expires_in_seconds);
        setIntervalSec(res.interval || 300);
        setLoading(false);
      } catch {
        if (!cancelled) setLoading(false);
      }
    };

    void refresh();
    timer = setInterval(() => {
      setExpires((s) => {
        if (s <= 1) {
          void refresh();
          return 0;
        }
        return s - 1;
      });
    }, 1000);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [familyGroupId]);

  const pct = intervalSec > 0 ? Math.max(0, Math.min(100, (expires / intervalSec) * 100)) : 0;

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5">
      <h3 className="font-semibold">Family code (TOTP)</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Ask the caller for this code during a suspicious call.
      </p>
      {loading ? (
        <Skeleton className="mt-4 h-12 w-40" />
      ) : (
        <>
          <p className="mt-4 font-mono text-4xl font-bold tracking-[0.3em]">{code}</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-emerald-400 transition-all duration-1000 linear"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Rotates in {expires}s</p>
        </>
      )}
    </div>
  );
}
