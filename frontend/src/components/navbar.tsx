"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { NAV_LINKS } from "@/lib/constants";

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Shield className="h-5 w-5 text-emerald-400" aria-hidden />
          <span>Mirage</span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
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

        <div className="flex items-center gap-3">
          <Badge
            variant="secondary"
            className="gap-1.5 font-mono"
            title="Resilience Score — real data arrives in Phase 3"
          >
            <Activity className="h-3 w-3 text-emerald-400" aria-hidden />
            Score 68
          </Badge>
        </div>
      </div>

      {/* Mobile nav */}
      <nav
        className="flex gap-1 overflow-x-auto border-t border-border/60 px-3 py-2 md:hidden"
        aria-label="Primary mobile"
      >
        {NAV_LINKS.map((link) => {
          const active =
            link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm ${
                active ? "bg-accent text-accent-foreground" : "text-muted-foreground"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
