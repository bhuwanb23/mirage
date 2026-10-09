"use client";

import { useState } from "react";
import { Siren, Play, RotateCcw, Globe } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { SCAM_TYPES, LANGUAGES } from "@/lib/constants";

type Phase = "setup" | "briefing" | "run" | "debrief";

const DEBRIEF = [
  {
    hook: "Authority",
    caught: true,
    note: 'You paused when "RBI officer" was used as pressure.',
  },
  {
    hook: "Urgency",
    caught: false,
    note: 'The 10-minute deadline pushed you to share the OTP. Missed.',
  },
  {
    hook: "Isolation",
    caught: false,
    note: "“Don’t tell family” kept you silent. Missed.",
  },
  {
    hook: "Payment",
    caught: true,
    note: "You refused the gift-card payment.",
  },
];

export default function DrillPage() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [scamType, setScamType] = useState<string>(SCAM_TYPES[0].id);
  const [lang, setLang] = useState<string>(LANGUAGES[0].id);
  const [name, setName] = useState("");

  const reset = () => setPhase("setup");
  const caught = DEBRIEF.filter((d) => d.caught).length;
  const score = Math.round((caught / DEBRIEF.length) * 100);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="flex items-center gap-3">
        <Siren className="h-6 w-6 text-emerald-400" aria-hidden />
        <h1 className="text-2xl font-bold tracking-tight">Scam Fire Drills</h1>
        <Badge variant="outline" className="font-mono text-[10px]">
          Phase 3
        </Badge>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        A simulated attack built from your exposure profile. You fail here so you
        don&apos;t fail for real.
      </p>

      <div className="mt-6 flex gap-2 text-xs">
        {(["setup", "briefing", "run", "debrief"] as const).map((p, i) => (
          <div
            key={p}
            className={`flex-1 rounded-md border px-2 py-1.5 text-center font-mono uppercase ${
              p === phase
                ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-400"
                : "border-border/60 text-muted-foreground"
            }`}
          >
            {i + 1}. {p}
          </div>
        ))}
      </div>

      {phase === "setup" && (
        <Card className="mt-6 border-border/60">
          <CardHeader>
            <CardTitle>Configure the drill</CardTitle>
            <CardDescription>
              Phase 0 ships the flow shell. Backend generation lands in Phase 3.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <label className="mb-2 block text-sm font-medium" htmlFor="drill-name">
                Name used by the scammer
              </label>
              <Input
                id="drill-name"
                placeholder="e.g. Priya"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div>
              <span className="mb-2 block text-sm font-medium">Scam type</span>
              <div className="flex flex-wrap gap-2">
                {SCAM_TYPES.map((t) => (
                  <Button
                    key={t.id}
                    size="sm"
                    variant={scamType === t.id ? "default" : "outline"}
                    onClick={() => setScamType(t.id)}
                  >
                    {t.label}
                  </Button>
                ))}
              </div>
            </div>

            <div>
              <span className="mb-2 block text-sm font-medium">Language</span>
              <div className="flex flex-wrap gap-2">
                {LANGUAGES.map((l) => (
                  <Button
                    key={l.id}
                    size="sm"
                    variant={lang === l.id ? "default" : "outline"}
                    onClick={() => setLang(l.id)}
                  >
                    {l.label}
                  </Button>
                ))}
              </div>
            </div>

            <Separator />
            <Button onClick={() => setPhase("briefing")} className="w-full">
              <Play className="mr-2 h-4 w-4" aria-hidden />
              Arm the drill
            </Button>
          </CardContent>
        </Card>
      )}

      {phase === "briefing" && (
        <Card className="mt-6 border-border/60">
          <CardHeader>
            <CardTitle>Briefing</CardTitle>
            <CardDescription>What is about to happen to you.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              An attacker knowing only that you are{" "}
              <span className="text-foreground">{name || "a target"}</span> will run a{" "}
              <span className="text-foreground">
                {SCAM_TYPES.find((t) => t.id === scamType)?.label}
              </span>{" "}
              in <span className="text-foreground">{lang.toUpperCase()}</span>.
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>Hook — an excuse to start the conversation.</li>
              <li>Authority — someone who outranks you.</li>
              <li>Isolation — keep it secret from family.</li>
              <li>Urgency — a ticking clock.</li>
              <li>Payment — the ask.</li>
            </ul>
            <div className="flex gap-3 pt-2">
              <Button onClick={() => setPhase("run")}>Start</Button>
              <Button variant="outline" onClick={reset}>
                Back
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {phase === "run" && (
        <Card className="mt-6 border-border/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-emerald-400" aria-hidden />
              Live drill
            </CardTitle>
            <CardDescription>
              Caller audio + SMS thread render here once Phase 3 wires the LLM.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-md border border-border/60 bg-accent/30 p-4 text-sm font-mono">
              <span className="text-emerald-400">SCAMMER:</span> Namaste, this is the
              bank KYC desk. Your account will be blocked in 10 minutes unless you
              confirm your OTP.
            </div>
            <div className="rounded-md border border-border/60 p-4 text-sm text-muted-foreground italic">
              Your responses, voice, and hesitation will be scored per hook.
            </div>
            <Button onClick={() => setPhase("debrief")}>End &amp; get debrief</Button>
          </CardContent>
        </Card>
      )}

      {phase === "debrief" && (
        <Card className="mt-6 border-border/60">
          <CardHeader>
            <CardTitle>Debrief</CardTitle>
            <CardDescription>Which hooks landed, which didn&apos;t.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-end gap-3">
              <span className="text-5xl font-bold font-mono">{score}</span>
              <span className="pb-2 text-sm text-muted-foreground">
                resilience from this drill
              </span>
            </div>
            <div className="space-y-2">
              {DEBRIEF.map((d) => (
                <div
                  key={d.hook}
                  className="flex items-start gap-3 rounded-md border border-border/60 p-3 text-sm"
                >
                  <Badge variant={d.caught ? "secondary" : "outline"} className="font-mono">
                    {d.caught ? "CAUGHT" : "MISSED"}
                  </Badge>
                  <div>
                    <div className="font-medium">{d.hook}</div>
                    <div className="text-muted-foreground">{d.note}</div>
                  </div>
                </div>
              ))}
            </div>
            <Button variant="outline" onClick={reset} className="w-full">
              <RotateCcw className="mr-2 h-4 w-4" aria-hidden />
              Run another drill
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
