"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TELEGRAM_BOT_URL } from "@/lib/constants";

export function LandingHero() {
  const reduce = useReducedMotion();

  return (
    <section className="relative overflow-hidden border-b border-border/60">
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(30,64,175,0.25),transparent_65%)]"
        animate={reduce ? undefined : { scale: [1, 1.05, 1] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="relative mx-auto flex max-w-6xl flex-col items-center px-4 py-20 text-center md:py-28">
        <motion.div
          initial={reduce ? false : { opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="mb-6 rounded-full bg-emerald-500/10 p-4 shadow-[0_0_40px_rgba(52,211,153,0.25)]"
        >
          <ShieldCheck className="h-12 w-12 text-emerald-400" aria-hidden />
        </motion.div>

        <motion.h1
          className="max-w-3xl text-4xl font-bold tracking-tight md:text-5xl"
          initial={reduce ? false : { opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          Mirage
        </motion.h1>
        <motion.p
          className="mt-3 max-w-2xl text-2xl font-semibold text-foreground/90 md:text-3xl"
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          Your personal AI immune system against scams
        </motion.p>
        <motion.p
          className="mt-4 max-w-xl text-base text-muted-foreground md:text-lg"
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          We attack you first, so real scammers can&apos;t.
        </motion.p>

        <motion.div
          className="mt-8 flex flex-col gap-3 sm:flex-row"
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55 }}
        >
          <Button size="lg" asChild className="min-h-11 px-5">
            <Link href="/drill">Start Your First Fire Drill</Link>
          </Button>
          <Button size="lg" variant="outline" asChild className="min-h-11 px-5">
            <a href={TELEGRAM_BOT_URL} target="_blank" rel="noopener noreferrer">
              Try the Bot
            </a>
          </Button>
        </motion.div>

        <motion.ul
          className="mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground"
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.75 }}
        >
          <li>✓ Free forever</li>
          <li>✓ No app install</li>
          <li>✓ English, Hindi, Tamil</li>
        </motion.ul>
      </div>
    </section>
  );
}
