"use client";

import { motion, useSpring } from "framer-motion";
import { AudioLines, BrainCircuit } from "lucide-react";
import type { VoiceUpdateMessage } from "@/lib/guardian-ws";

/** Colour of the gauge by score band (plan §4.4 interpretation table). */
function bandColor(score: number): string {
  if (score <= 0.3) return "bg-emerald-500";
  if (score <= 0.5) return "bg-yellow-500";
  if (score <= 0.7) return "bg-orange-500";
  return "bg-red-500";
}

export function VoiceAuthenticity({
  voice,
  simulatedScore,
}: {
  voice: VoiceUpdateMessage | null;
  /** In sim mode the injected score drives the meter instead. */
  simulatedScore?: number;
}) {
  const useSim = simulatedScore !== undefined && simulatedScore !== null;
  const rawScore = useSim ? simulatedScore : (voice?.synthetic_score ?? 0);
  const available = useSim || (voice?.available ?? false);
  const ready = useSim || (voice?.ready ?? false);
  const label = useSim
    ? simulatedScore > 0.7
      ? "Likely AI Clone (simulated)"
      : simulatedScore > 0.5
        ? "Uncertain (simulated)"
        : "Likely Human (simulated)"
    : ready
      ? (voice?.label ?? "—")
      : "Analyzing…";

  const spring = useSpring(rawScore * 100, { stiffness: 60, damping: 18 });
  spring.set(rawScore * 100);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium">
          <AudioLines className="h-4 w-4 text-emerald-400" aria-hidden />
          Voice authenticity
        </span>
        <span className="font-mono text-xs text-muted-foreground">
          AI&nbsp;{Math.round(rawScore * 100)}%
        </span>
      </div>

      {!available ? (
        <div className="rounded-md border border-border/60 bg-muted/30 p-3 text-xs text-muted-foreground">
          {voice?.quality_warning ??
            "Voice analysis unavailable on this server — transcription still works."}
        </div>
      ) : (
        <>
          <div className="relative h-3 overflow-hidden rounded-full bg-muted">
            <motion.div
              className={`h-full rounded-full ${bandColor(rawScore)}`}
              style={{ width: spring }}
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Human</span>
            <span className="flex items-center gap-1 font-medium text-foreground">
              {!useSim && voice?.method === "resemblyzer" && (
                <BrainCircuit className="h-3 w-3" aria-hidden />
              )}
              {label}
            </span>
            <span>AI Clone</span>
          </div>
          {!useSim && voice?.quality_warning && (
            <p className="text-xs text-amber-400">⚠ {voice.quality_warning}</p>
          )}
          {!useSim && !ready && (
            <p className="text-xs text-muted-foreground">
              Analyzing voice… score appears after 3 chunks (~12 s).
            </p>
          )}
        </>
      )}
    </div>
  );
}
