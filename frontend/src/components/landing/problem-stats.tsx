"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";

const STATS = [
  { value: 7000, suffix: "Cr", prefix: "₹", label: "lost to scams in India (2024)" },
  { value: 33, suffix: "%", prefix: "", label: "of Indians targeted in 2024" },
  { value: 85, suffix: "%", prefix: "", label: "of scam victims are 50+ years old" },
];

function CountUp({
  value,
  prefix,
  suffix,
  active,
}: {
  value: number;
  prefix: string;
  suffix: string;
  active: boolean;
}) {
  const [n, setN] = useState(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!active) return;
    if (reduce) {
      // Animate-less path: jump straight to the target.
      setN(value);
      return;
    }
    const start = performance.now();
    const duration = 1200;
    let frame = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      setN(Math.round(value * p));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- value read inside rAF body; fine for this effect
  }, [active, value]);

  return (
    <span className="font-mono text-4xl font-bold text-red-400">
      {prefix}
      {n.toLocaleString("en-IN")}
      {suffix}
    </span>
  );
}

export function ProblemStats() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.25 });
  const [mounted, setMounted] = useState(false);
  const reduce = useReducedMotion();

  // Fallback: if IntersectionObserver misses (SSR/crawlers/odd viewports),
  // still animate shortly after mount so stats never stay at 0.
  useEffect(() => {
    const t = window.setTimeout(() => setMounted(true), 400);
    return () => window.clearTimeout(t);
  }, []);

  const active = inView || mounted;

  return (
    <section ref={ref} className="mx-auto max-w-6xl px-4 py-16 md:py-20">
      <h2 className="text-2xl font-semibold md:text-3xl">The Problem</h2>
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {STATS.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={active ? { opacity: 1, y: 0 } : undefined}
            transition={{ delay: i * 0.1 }}
            className="rounded-xl border border-border/60 bg-card/40 p-6"
          >
            <CountUp
              value={stat.value}
              prefix={stat.prefix}
              suffix={stat.suffix}
              active={active}
            />
            <p className="mt-2 text-sm text-muted-foreground">{stat.label}</p>
          </motion.div>
        ))}
      </div>
      <p className="mt-8 max-w-2xl text-muted-foreground">
        Current solutions detect scams after you&apos;ve been targeted. Mirage trains
        you before.
      </p>
    </section>
  );
}
