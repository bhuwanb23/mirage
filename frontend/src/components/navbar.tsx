"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Menu, Shield, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getUserId } from "@/lib/auth";
import { NAV_LINKS } from "@/lib/constants";

export function Navbar() {
  const pathname = usePathname();
  const [score, setScore] = useState<number | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const userId = getUserId();
    api
      .drillScore(userId)
      .then((data) => {
        if (!cancelled) setScore(data.current_score);
      })
      .catch(() => {
        if (!cancelled) setScore(null);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  // Collapse the nav panel whenever the route changes — die setup.
  useEffect(() => {
    setOpen(false);
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-border/70 bg-background/85 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link
          href="/"
          className="flex items-center gap-2.5 font-semibold tracking-tight transition-opacity hover:opacity-90"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/15 ring-1 ring-emerald-500/30">
            <Shield className="h-5 w-5 text-emerald-400" aria-hidden />
          </span>
          <span className="text-gradient-brand text-lg">Mirage</span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                }`}
                aria-current={active ? "page" : undefined}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Badge
            variant="secondary"
            className="hidden gap-1.5 border border-emerald-500/20 bg-emerald-500/10 font-mono text-emerald-100 sm:inline-flex"
            title="Resilience Score"
          >
            <Activity className="h-3 w-3 text-emerald-400" aria-hidden />
            Score {score ?? "—"}
          </Badge>
          <Button size="sm" className="hidden md:inline-flex" asChild>
            <Link href="/drill">Start drill</Link>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {open ? (
        <nav
          className="flex flex-col gap-1 border-t border-border/60 px-3 py-3 md:hidden"
          aria-label="Primary mobile"
        >
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-3 py-2.5 text-sm ${
                  active ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      ) : null}
    </header>
  );
}
