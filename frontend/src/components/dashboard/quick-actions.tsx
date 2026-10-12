"use client";

import Link from "next/link";
import { Flame, Network, Shield, Users } from "lucide-react";
import { TELEGRAM_BOT_URL } from "@/lib/constants";

const ACTIONS = [
  {
    href: "/drill",
    label: "New Fire Drill",
    desc: "Train against a personalized scam",
    icon: Flame,
    primary: true,
  },
  {
    href: "/guardian",
    label: "Start Guardian",
    desc: "Live call stage tracking",
    icon: Shield,
  },
  {
    href: TELEGRAM_BOT_URL,
    label: "Open Bot",
    desc: "Check a message on Telegram",
    icon: Flame,
    external: true,
  },
  {
    href: "/family",
    label: "Family Settings",
    desc: "Memory Handshake + alerts",
    icon: Users,
  },
  {
    href: "/graph",
    label: "View Scam Graph",
    desc: "Rings, map, and reports",
    icon: Network,
  },
];

export function QuickActions() {
  return (
    <div className="glass-panel p-5 md:p-6">
      <h3 className="text-lg font-semibold">Quick Actions</h3>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {ACTIONS.map((action) => {
          const Icon = action.icon;
          const className = `flex min-h-14 items-start gap-3 rounded-lg border px-3 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            action.primary
              ? "border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/15"
              : "border-border/60 hover:bg-muted/40"
          }`;
          const inner = (
            <>
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
              <span>
                <span className="block text-sm font-medium">{action.label}</span>
                <span className="block text-xs text-muted-foreground">{action.desc}</span>
              </span>
            </>
          );
          if (action.external) {
            return (
              <a
                key={action.label}
                href={action.href}
                target="_blank"
                rel="noopener noreferrer"
                className={className}
              >
                {inner}
              </a>
            );
          }
          return (
            <Link key={action.label} href={action.href} className={className}>
              {inner}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
