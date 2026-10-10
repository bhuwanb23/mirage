"use client";

import { CheckCircle2, XCircle, Lightbulb, Compass } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DebriefStageDetail, DrillDebrief } from "@/lib/drill-api";

function StageDetail({ item, caught }: { item: DebriefStageDetail; caught: boolean }) {
  return (
    <div className="rounded-md border border-border/60 p-3 text-sm">
      <div className="flex items-center gap-2">
        <Badge variant={caught ? "default" : "outline"} className="font-mono">
          {caught ? "CAUGHT" : "MISSED"}
        </Badge>
        <span className="font-medium capitalize">{item.stage}</span>
        {item.timestamp && (
          <span className="ml-auto font-mono text-xs text-muted-foreground">
            {item.timestamp}
          </span>
        )}
      </div>
      <p className="mt-2 text-muted-foreground">{item.what_happened}</p>
      <p className="mt-1">
        <span className="font-medium">Why it works: </span>
        <span className="text-muted-foreground">{item.why_it_works}</span>
      </p>
      <p className="mt-1">
        <span className="font-medium text-emerald-400">Real-world: </span>
        <span className="text-muted-foreground">{item.real_world_tip}</span>
      </p>
    </div>
  );
}

const OUTCOME_STYLES: Record<string, { label: string; className: string }> = {
  success: { label: "SCAM SPOTTED", className: "bg-emerald-500/15 text-emerald-400" },
  partial: { label: "CLOSE CALL", className: "bg-amber-500/15 text-amber-400" },
  failed: { label: " Fell for it", className: "bg-red-500/15 text-red-400" },
};

export function DrillDebriefView({ debrief }: { debrief: DrillDebrief }) {
  const outcome = OUTCOME_STYLES[debrief.outcome] ?? OUTCOME_STYLES.partial;

  return (
    <div className="mt-6 space-y-5">
      <div className="rounded-xl border border-border/60 bg-card p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Badge className={`font-mono ${outcome.className}`}>{outcome.label}</Badge>
          <span className="text-lg font-semibold">{debrief.headline}</span>
        </div>
        {debrief.reaction_assessment && (
          <p className="mt-2 text-sm text-muted-foreground">{debrief.reaction_assessment}</p>
        )}
      </div>

      {debrief.stages_caught.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-400">
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            Red flags you caught ({debrief.stages_caught.length})
          </h3>
          <div className="space-y-2">
            {debrief.stages_caught.map((s) => (
              <StageDetail key={`caught-${s.stage}`} item={s} caught />
            ))}
          </div>
        </div>
      )}

      {debrief.stages_missed.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-red-400">
            <XCircle className="h-4 w-4" aria-hidden />
            Tactics that slipped past you ({debrief.stages_missed.length})
          </h3>
          <div className="space-y-2">
            {debrief.stages_missed.map((s) => (
              <StageDetail key={`missed-${s.stage}`} item={s} caught={false} />
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border/60 bg-card p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Lightbulb className="h-4 w-4 text-amber-400" aria-hidden />
            Key lesson
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">{debrief.key_lesson}</p>
        </div>
        <div className="rounded-xl border border-border/60 bg-card p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Compass className="h-4 w-4 text-emerald-400" aria-hidden />
            If this happens for real
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">{debrief.real_world_action}</p>
        </div>
      </div>

      {debrief.encouragement && (
        <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-center text-sm text-emerald-400">
          {debrief.encouragement}
        </p>
      )}
    </div>
  );
}
