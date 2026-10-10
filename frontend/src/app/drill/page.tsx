"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, RotateCcw, Siren, LayoutDashboard } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DrillSetup, type DrillFormValues } from "@/components/drill/drill-setup";
import { DrillPlayer, type DrillFinish } from "@/components/drill/drill-player";
import { DrillDebriefView } from "@/components/drill/drill-debrief";
import { ScoreCard, ScoreChart } from "@/components/drill/score-card";
import {
  drillApi,
  getUserId,
  mediaUrl,
  pregeneratedAudioUrl,
  FALLBACK_SCAM_TYPES,
  type DrillProfileOut,
  type DrillRespondOut,
  type DrillScoreOut,
  type DrillScriptOut,
  type ScamTypeInfo,
} from "@/lib/drill-api";
import { SCAM_TYPES } from "@/lib/constants";

type Phase = "setup" | "briefing" | "run" | "debrief";

const PHASES: Phase[] = ["setup", "briefing", "run", "debrief"];

function scamLabel(id: string): string {
  return (
    SCAM_TYPES.find((t) => t.id === id)?.label ??
    id.replace(/_/g, " ")
  );
}

export default function DrillPage() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [scamTypes, setScamTypes] = useState<ScamTypeInfo[]>(FALLBACK_SCAM_TYPES);
  const [profile, setProfile] = useState<DrillProfileOut | null>(null);
  const [script, setScript] = useState<DrillScriptOut | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioNotice, setAudioNotice] = useState<string | null>(null);
  const [result, setResult] = useState<DrillRespondOut | null>(null);
  const [score, setScore] = useState<DrillScoreOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formInitial, setFormInitial] = useState<Partial<DrillFormValues> | undefined>();

  // load supported scam types (fallback list stands in if backend is down)
  useEffect(() => {
    let cancelled = false;
    drillApi
      .getScamTypes()
      .then((data) => {
        if (!cancelled && data.scam_types?.length) setScamTypes(data.scam_types);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const userId = getUserId();

  const armDrill = useCallback(
    async (values: DrillFormValues) => {
      setBusy(true);
      setError(null);
      try {
        const prof = await drillApi.createProfile({
          name: values.name,
          city: values.city || undefined,
          bank: values.bank,
          employer: values.employer || undefined,
          relative_name: values.relativeName || undefined,
          relative_relation: values.relativeRelation || undefined,
          language: values.language,
          user_id: userId,
        });
        setProfile(prof);

        if (values.voiceFile) {
          try {
            await drillApi.uploadVoice(prof.profile_id, values.voiceFile);
          } catch (err) {
            // voice cloning is optional — fall through to edge-tts
            console.warn("voice upload failed, using standard voice", err);
          }
        }

        const scr = await drillApi.generateScript({
          profile_id: prof.profile_id,
          scam_type: values.scamType,
          difficulty: values.difficulty,
        });
        setScript(scr);
        setFormInitial(values);

        // synthesize voice (edge-tts). On failure, try pre-generated demo
        // audio, then text-only drill. Never block the demo.
        setAudioUrl(null);
        setAudioNotice(null);
        try {
          const synth = await drillApi.synthesizeVoice({ script_id: scr.script_id });
          if (synth.status === "ready" && synth.audio_url) {
            setAudioUrl(mediaUrl(synth.audio_url));
          } else {
            throw new Error(synth.message || "synthesis failed");
          }
        } catch {
          setAudioUrl(pregeneratedAudioUrl(scr.scam_type));
          setAudioNotice(
            "Live voice generation unavailable — using pre-generated demo audio (or text-only if that fails).",
          );
        }

        setPhase("briefing");
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(
          message.includes("Failed to fetch")
            ? "Cannot reach the backend. Start it with: cd backend && uv run uvicorn app.main:app --port 8000"
            : message,
        );
      } finally {
        setBusy(false);
      }
    },
    [userId],
  );

  const finishDrill = useCallback(
    async (finish: DrillFinish) => {
      if (!script) return;
      setScoring(true);
      setError(null);
      try {
        const out = await drillApi.respond({
          script_id: script.script_id,
          user_action: finish.action,
          reaction_time_seconds: finish.reactionTimeSeconds,
          audio_position_seconds: finish.audioPositionSeconds,
        });
        setResult(out);
        try {
          setScore(await drillApi.getScore(userId));
        } catch {
          setScore(null); // score card still shows per-drill numbers
        }
        setPhase("debrief");
      } catch (err) {
        setError(
          `Could not save the drill result: ${err instanceof Error ? err.message : String(err)}`,
        );
      } finally {
        setScoring(false);
      }
    },
    [script, userId],
  );

  const reset = () => {
    setPhase("setup");
    setProfile(null);
    setScript(null);
    setResult(null);
    setAudioUrl(null);
    setAudioNotice(null);
    setError(null);
  };

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
        {PHASES.map((p, i) => (
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
        <DrillSetup
          scamTypes={scamTypes}
          initial={formInitial}
          busy={busy}
          error={error}
          onSubmit={armDrill}
        />
      )}

      {phase === "briefing" && script && (
        <Card className="mt-6 border-border/60">
          <CardHeader>
            <CardTitle>{script.title}</CardTitle>
            <CardDescription>
              A {script.difficulty_level} {scamLabel(script.scam_type)} call, personalized
              for {profile?.name ?? "you"} in {script.language.toUpperCase()} — about{" "}
              {Math.round(script.estimated_duration_seconds)}s. Generated from{" "}
              {script.source === "llm" ? "live AI" : "a vetted template"}.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
              <li>Hook — an excuse to start the conversation.</li>
              <li>Authority — someone who outranks you.</li>
              <li>Isolation — keep it secret from family.</li>
              <li>Urgency — a ticking clock.</li>
              <li>Payment — the ask.</li>
            </ul>
            <div className="rounded-md border border-border/60 bg-accent/30 p-3">
              <span className="text-xs font-medium uppercase text-muted-foreground">
                Planted red flags you&apos;ll need to catch
              </span>
              <ul className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">
                {script.red_flags_planted.slice(0, 6).map((flag) => (
                  <li key={flag} className="flex items-start gap-1.5">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                    {flag}
                  </li>
                ))}
              </ul>
            </div>
            {audioNotice && (
              <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-400">
                {audioNotice}
              </p>
            )}
            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <div className="flex gap-3 pt-1">
              <Button size="lg" onClick={() => setPhase("run")}>
                🔥 Start Fire Drill
              </Button>
              <Button variant="outline" onClick={reset}>
                Back
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {phase === "run" && script && (
        <>
          <DrillPlayer
            audioUrl={audioUrl}
            stages={script.stages}
            fallbackDurationSeconds={script.estimated_duration_seconds}
            showStageHints={script.difficulty_level !== "hard"}
            scamLabel={scamLabel(script.scam_type)}
            onFinish={finishDrill}
          />
          {scoring && (
            <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Scoring your reaction and writing the debrief…
            </div>
          )}
          {error && (
            <p className="mt-4 text-center text-sm text-red-400" role="alert">
              {error}
            </p>
          )}
        </>
      )}

      {phase === "debrief" && result && (
        <>
          <ScoreCard result={result} score={score} />
          <DrillDebriefView debrief={result.debrief} />
          <ScoreChart score={score} />
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Button variant="outline" onClick={reset} className="flex-1" size="lg">
              <RotateCcw className="mr-2 h-4 w-4" aria-hidden />
              Run another drill
            </Button>
            <Button asChild size="lg" className="flex-1">
              <Link href="/dashboard">
                <LayoutDashboard className="mr-2 h-4 w-4" aria-hidden />
                Back to Dashboard
              </Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
