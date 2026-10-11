"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export function FinalCta() {
  return (
    <section className="border-t border-border/60 bg-gradient-to-br from-emerald-950/40 to-sky-950/30 py-16 md:py-20">
      <div className="mx-auto flex max-w-6xl flex-col items-center px-4 text-center">
        <h2 className="text-2xl font-semibold md:text-3xl">Ready to become scam-proof?</h2>
        <Button size="lg" asChild className="mt-6 min-h-11 px-6">
          <Link href="/drill">Start Your First Fire Drill — It takes 2 minutes</Link>
        </Button>
        <p className="mt-4 text-sm text-muted-foreground">
          Free · No signup required · Works on mobile
        </p>
      </div>
    </section>
  );
}
