"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

type Props = {
  title: string;
  value: string | number;
  suffix?: string;
  change?: number;
  changeLabel?: string;
  icon?: ReactNode;
  href?: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
};

export function StatCard({
  title,
  value,
  suffix,
  change,
  changeLabel,
  icon,
  href,
  loading,
  error,
  onRetry,
}: Props) {
  const body = (
    <div className="glass-panel relative p-5 transition hover:border-emerald-500/25 hover:shadow-emerald-950/20">
      {icon ? (
        <div className="absolute right-4 top-4 text-muted-foreground/40" aria-hidden>
          {icon}
        </div>
      ) : null}
      <p className="text-sm text-muted-foreground">{title}</p>
      {loading ? (
        <Skeleton className="mt-3 h-9 w-20" />
      ) : error ? (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-red-400">Data unavailable</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="text-xs text-emerald-400 hover:underline"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : (
        <>
          <p className="mt-2 font-mono text-3xl font-bold">
            {value}
            {suffix ? (
              <span className="text-base font-normal text-muted-foreground">{suffix}</span>
            ) : null}
          </p>
          {typeof change === "number" ? (
            <p
              className={`mt-2 flex items-center gap-1 text-xs ${
                change >= 0 ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {change >= 0 ? (
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
              ) : (
                <ArrowDownRight className="h-3.5 w-3.5" aria-hidden />
              )}
              {change >= 0 ? "+" : ""}
              {change}
              {changeLabel ? ` ${changeLabel}` : ""}
            </p>
          ) : null}
        </>
      )}
    </div>
  );

  if (href && !loading && !error) {
    return (
      <Link href={href} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        {body}
      </Link>
    );
  }
  return body;
}
