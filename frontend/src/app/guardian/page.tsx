"use client";

import { useState } from "react";
import { PhoneCall, Mic, MicOff, KeyRound, ShieldCheck } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

const STAGES = [
  { id: "hook", label: "Hook", desc: "Excuse to start the call." },
  { id: "authority", label: "Authority", desc: "Claims rank or institution." },
  { id: "isolation", label: "Isolation", desc: "Demands secrecy from family." },
  { id: "urgency", label: "Urgency", desc: "A countdown you must obey." },
  { id: "payment", label: "Payment", desc: "The actual ask." },
];

export default function GuardianPage() {
  const [armed, setArmed] = useState(false);
  const [stageIdx, setStageIdx] = useState(2);
  const [secretSet, setSecretSet] = useState(false);

  const risk = Math.min(100, (stageIdx + 1) * 20);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="flex items-center gap-3">
        <PhoneCall className="h-6 w-6 text-emerald-400" aria-hidden />
        <h1 className="text-2xl font-bold tracking-tight">Live Call Guardian</h1>
        <Badge variant="outline" className="font-mono text-[10px]">
          Phase 4
        </Badge>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        On-device transcription feeds a 5-stage pipeline. The moment the scam
        reaches a recognized stage, Mirage speaks up.
      </p>

      <Card className="mt-6 border-border/60">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Call risk</span>
            <span className="font-mono text-2xl text-emerald-400">{risk}%</span>
          </CardTitle>
          <CardDescription>
            Pipeline position — placeholder feed until Phase 4 wires the audio
            pipeline.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Progress value={risk} className="h-2" />
          <div className="space-y-2">
            {STAGES.map((s, i) => {
              const active = i === stageIdx;
              const passed = i < stageIdx;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setStageIdx(i)}
                  className={`flex w-full items-start gap-3 rounded-md border p-3 text-left text-sm transition-colors ${
                    active
                      ? "border-emerald-500/60 bg-emerald-500/10"
                      : "border-border/60 hover:bg-accent/50"
                  }`}
                >
                  <span className="font-mono text-xs text-muted-foreground">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="flex-1">
                    <span className="flex items-center gap-2 font-medium">
                      {s.label}
                      {passed && (
                        <Badge variant="secondary" className="text-[10px]">
                          seen
                        </Badge>
                      )}
                    </span>
                    <span className="text-muted-foreground">{s.desc}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center justify-between rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <span className="flex items-center gap-2">
              <MicOff className="h-4 w-4 text-amber-400" aria-hidden />
              {armed ? "Listening — guard active" : "Guardian disarmed"}
            </span>
            <Button size="sm" onClick={() => setArmed((v) => !v)}>
              {armed ? "Stop" : "Arm guardian"}
            </Button>
          </div>

          <Separator />

          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <KeyRound className="h-4 w-4 text-emerald-400" aria-hidden />
              Memory Handshake
            </div>
            <p className="text-sm text-muted-foreground">
              A secret only your family knows. If the caller can&apos;t answer it,
              they aren&apos;t family — no matter what caller ID says.
            </p>
            <div className="flex gap-3">
              <Button
                size="sm"
                variant={secretSet ? "secondary" : "default"}
                onClick={() => setSecretSet(true)}
              >
                <ShieldCheck className="mr-2 h-4 w-4" aria-hidden />
                {secretSet ? "Handshake armed" : "Set handshake"}
              </Button>
              <Button size="sm" variant="ghost" disabled>
                <Mic className="mr-2 h-4 w-4" aria-hidden />
                Test voice match
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
