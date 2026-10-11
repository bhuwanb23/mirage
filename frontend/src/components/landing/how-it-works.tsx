"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { Flame, Network, Shield } from "lucide-react";

const STEPS = [
  {
    href: "/drill",
    icon: Flame,
    title: "Scam Fire Drill",
    body: "We simulate a real scam using your details so you learn to spot the signs.",
    cta: "Try it →",
    color: "text-amber-400",
  },
  {
    href: "/guardian",
    icon: Shield,
    title: "Live Guardian",
    body: "Monitors your calls in real time and alerts you before you pay.",
    cta: "Try it →",
    color: "text-emerald-400",
  },
  {
    href: "/graph",
    icon: Network,
    title: "Scam Intelligence",
    body: "Tracks scammer networks and warns your community.",
    cta: "View →",
    color: "text-sky-400",
  },
];

export function HowItWorks() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.2 });
  const [mounted, setMounted] = useState(false);
  const reduce = useReducedMotion();

  useEffect(() => {
    const t = window.setTimeout(() => setMounted(true), 400);
    return () => window.clearTimeout(t);
  }, []);

  const active = inView || mounted;

  return (
    <section ref={ref} className="border-y border-border/60 bg-card/20 py-16 md:py-20">
      <div className="mx-auto max-w-6xl px-4">
        <h2 className="text-2xl font-semibold md:text-3xl">How Mirage Protects You</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <motion.div
                key={step.title}
                initial={reduce ? false : { opacity: 0, x: -24 }}
                animate={active ? { opacity: 1, x: 0 } : undefined}
                transition={{ delay: i * 0.15 }}
                className="relative rounded-xl border border-border/60 bg-background/60 p-6 transition hover:-translate-y-1 hover:border-emerald-500/40"
              >
                <span className="absolute right-4 top-2 text-6xl font-bold text-muted/20">
                  {i + 1}
                </span>
                <Icon className={`h-10 w-10 ${step.color}`} aria-hidden />
                <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{step.body}</p>
                <Link
                  href={step.href}
                  className="mt-4 inline-block text-sm font-medium text-emerald-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {step.cta}
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
