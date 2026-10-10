"use client";

import { motion } from "framer-motion";
import type { AlertLevel, ScamStage } from "@/lib/guardian-ws";

const STAGES: { id: ScamStage; label: string; desc: string }[] = [
  { id: "hook", label: "Hook", desc: "Excuse to start the call." },
  { id: "authority", label: "Authority", desc: "Claims rank or institution." },
  { id: "isolation", label: "Isolation", desc: "Demands secrecy from family." },
  { id: "urgency", label: "Urgency", desc: "A countdown you must obey." },
  { id: "payment", label: "Payment", desc: "The actual ask." },
];

const ORDER: ScamStage[] = ["none", "hook", "authority", "isolation", "urgency", "payment"];

/** Per-stage fill colour, per plan §4.3. */
const STAGE_COLORS: Record<string, string> = {
  hook: "bg-green-500",
  authority: "bg-green-500",
  isolation: "bg-yellow-500",
  urgency: "bg-orange-500",
  payment: "bg-red-500",
};

const ICONS: Record<AlertLevel, string> = {
  safe: "⬜",
  suspicious: "🟨",
  warning: "🟧",
  critical: "🟥",
};

function stageIcon(stage: ScamStage, current: ScamStage, reached: boolean): string {
  if (stage === current && stage !== "none") return "🟥";
  if (reached) return "🟩";
  return "⬜";
}

export function StageTracker({
  currentStage,
  confidence,
  alertLevel,
  durationSeconds,
  stageTimestamps,
}: {
  currentStage: ScamStage;
  confidence: number;
  alertLevel: AlertLevel;
  durationSeconds: number;
  stageTimestamps: Record<string, number | null>;
}) {
  const currentRank = ORDER.indexOf(currentStage);
  const minutes = Math.floor(durationSeconds / 60);
  const seconds = Math.floor(durationSeconds % 60);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Scam Stage Tracker</span>
        <span className="font-mono text-xs text-muted-foreground">
          {minutes}:{String(seconds).padStart(2, "0")}
        </span>
      </div>

      <div className="space-y-2">
        {STAGES.map((stage, idx) => {
          const rank = idx + 1;
          const reached = currentRank >= rank;
          const active = currentRank === rank;
          const fill = reached ? STAGE_COLORS[stage.id] : "bg-muted";
          const stamp = stageTimestamps[stage.id];

          return (
            <div
              key={stage.id}
              className={`rounded-md border p-2.5 transition-colors ${
                active
                  ? "border-emerald-500/60 bg-emerald-500/5"
                  : "border-border/60"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="w-4 text-xs" aria-hidden>
                  {stageIcon(stage.id, currentStage, reached)}
                </span>
                <span className="w-16 text-sm font-medium">{stage.label}</span>
                <div
                  className="h-2 flex-1 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-valuenow={reached ? 100 : 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${stage.label} stage`}
                >
                  <motion.div
                    className={`h-full rounded-full ${fill} ${
                      active ? "shadow-[0_0_8px_rgba(16,185,129,0.6)]" : ""
                    }`}
                    initial={{ width: 0 }}
                    animate={{ width: reached ? "100%" : "0%" }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  />
                </div>
                <span className="w-14 text-right font-mono text-[10px] text-muted-foreground">
                  {stamp !== null && stamp !== undefined ? `${stamp}s` : reached ? "…" : ""}
                </span>
              </div>
              {active && (
                <p className="mt-1 pl-7 text-xs text-muted-foreground">{stage.desc}</p>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2 text-sm">
        <span className="text-muted-foreground">
          Current:{" "}
          <span className="font-mono uppercase text-foreground">{currentStage}</span>
        </span>
        <span className="flex items-center gap-3">
          <span className="text-muted-foreground">
            Confidence{" "}
            <span className="font-mono text-foreground">
              {Math.round(confidence * 100)}%
            </span>
          </span>
          <span title={`alert: ${alertLevel}`} aria-label={`alert level ${alertLevel}`}>
            {ICONS[alertLevel]}
          </span>
        </span>
      </div>
    </div>
  );
}
