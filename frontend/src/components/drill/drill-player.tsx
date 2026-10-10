"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Phone, PhoneOff, ShieldAlert, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DrillStage, DrillUserAction } from "@/lib/drill-api";

type RunState = "countdown" | "ringing" | "playing" | "ended";

export interface DrillFinish {
  action: DrillUserAction;
  reactionTimeSeconds: number;
  audioPositionSeconds: number;
}

const STAGE_LABELS: Record<string, string> = {
  hook: "Hook",
  authority: "Authority",
  isolation: "Isolation",
  urgency: "Urgency",
  payment: "Payment",
};

function fmt(seconds: number): string {
  const s = Math.max(Math.round(seconds), 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Telephone-band EQ (300–3400 Hz) so the synthetic voice sounds like a real
 * phone line. Applied only when the browser gives us an AudioContext with
 * confirmed user activation; any failure leaves plain playback untouched.
 */
function applyPhoneEq(el: HTMLAudioElement): (() => void) | null {
  try {
    if (typeof navigator !== "undefined" && !navigator.userActivation?.hasBeenActive) {
      return null; // no gesture yet — routing through a suspended context = silence
    }
    const ctx = new AudioContext();
    const src = ctx.createMediaElementSource(el);
    const hp = ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 300;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 3400;
    src.connect(hp);
    hp.connect(lp);
    lp.connect(ctx.destination);
    void ctx.resume().catch(() => undefined);
    return () => {
      try {
        src.disconnect();
        lp.disconnect();
        void ctx.close();
      } catch {
        /* already torn down */
      }
    };
  } catch {
    return null;
  }
}

/** Indian phone ring: dual-tone 425+450 Hz, 400ms on / 200ms off, ~2.4s. */
function playRingTone(): () => void {
  try {
    const ctx = new AudioContext();
    const gain = ctx.createGain();
    gain.gain.value = 0;
    gain.connect(ctx.destination);
    const o1 = ctx.createOscillator();
    const o2 = ctx.createOscillator();
    o1.frequency.value = 425;
    o2.frequency.value = 450;
    o1.connect(gain);
    o2.connect(gain);
    o1.start();
    o2.start();
    const t0 = ctx.currentTime;
    for (let i = 0; i < 4; i++) {
      const on = t0 + i * 0.6;
      gain.gain.setValueAtTime(0.0001, on);
      gain.gain.exponentialRampToValueAtTime(0.15, on + 0.02);
      gain.gain.setValueAtTime(0.15, on + 0.38);
      gain.gain.exponentialRampToValueAtTime(0.0001, on + 0.4);
    }
    const end = t0 + 2.4;
    o1.stop(end);
    o2.stop(end);
    return () => {
      try {
        o1.stop();
        o2.stop();
      } catch {
        /* already stopped */
      }
      void ctx.close().catch(() => undefined);
    };
  } catch {
    return () => undefined;
  }
}

export function DrillPlayer({
  audioUrl,
  stages,
  fallbackDurationSeconds,
  showStageHints,
  scamLabel,
  onFinish,
}: {
  audioUrl: string | null;
  stages: DrillStage[];
  fallbackDurationSeconds: number;
  showStageHints: boolean;
  scamLabel: string;
  onFinish: (result: DrillFinish) => void;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const startedAtRef = useRef<number>(0);
  const pausedAtRef = useRef<number | null>(null);
  const pausedTotalRef = useRef(0);
  const finishedRef = useRef(false);
  const onFinishRef = useRef(onFinish);
  useEffect(() => {
    onFinishRef.current = onFinish;
  }, [onFinish]);

  const [runState, setRunState] = useState<RunState>("countdown");
  const [countdown, setCountdown] = useState(3);
  const [position, setPosition] = useState(0);
  const [reaction, setReaction] = useState(0);
  const [duration, setDuration] = useState(fallbackDurationSeconds);
  const [audioError, setAudioError] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  const textOnly = !audioUrl || audioError;
  const active = runState === "playing";

  const currentStage = useMemo(() => {
    return (
      stages.find(
        (s) => position >= s.start_seconds && position < s.end_seconds,
      ) ?? null
    );
  }, [stages, position]);

  const finish = useCallback(
    (action: DrillUserAction) => {
      if (finishedRef.current) return;
      finishedRef.current = true;
      setRunState("ended");
      const audio = audioRef.current;
      const pos = textOnly ? position : (audio?.currentTime ?? position);
      audio?.pause();
      const reactionTime =
        action === "identified_scam"
          ? Math.max((performance.now() - startedAtRef.current - pausedTotalRef.current) / 1000, 0)
          : Math.round(pos * 10) / 10;
      onFinishRef.current({
        action,
        reactionTimeSeconds: Math.round(reactionTime * 10) / 10,
        audioPositionSeconds: Math.round(pos * 10) / 10,
      });
    },
    [position, textOnly],
  );

  // telephone EQ on the scam audio (best effort, silent fallback)
  useEffect(() => {
    if (textOnly || runState === "ended") return;
    const el = audioRef.current;
    if (!el) return;
    return applyPhoneEq(el) ?? undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- apply once per element
  }, [textOnly]);

  // countdown -> ring -> play
  useEffect(() => {
    if (runState !== "countdown") return;
    if (countdown <= 0) {
      const t = setTimeout(() => setRunState("ringing"), 0);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setCountdown((c) => c - 1), 800);
    return () => clearTimeout(t);
  }, [runState, countdown]);

  useEffect(() => {
    if (runState !== "ringing") return;
    const stopRing = playRingTone();
    const t = setTimeout(() => {
      stopRing();
      startedAtRef.current = performance.now();
      pausedTotalRef.current = 0;
      pausedAtRef.current = null;
      setRunState("playing");
      if (!textOnly) {
        void audioRef.current?.play().catch(() => setAudioError(true));
      }
    }, 2400);
    return () => {
      clearTimeout(t);
      stopRing();
    };
  }, [runState, textOnly]);

  // reaction/progress ticker (rAF; audio position when available)
  useEffect(() => {
    if (runState !== "playing") return;
    let raf = 0;
    const tick = () => {
      const audio = audioRef.current;
      if (!textOnly && audio && !audio.paused) {
        setPosition(audio.currentTime);
        if (audio.duration && Number.isFinite(audio.duration)) {
          setDuration(audio.duration);
        }
      } else if (textOnly && pausedAtRef.current === null) {
        const elapsed =
          (performance.now() - startedAtRef.current - pausedTotalRef.current) / 1000;
        setPosition(elapsed);
        if (elapsed >= fallbackDurationSeconds) {
          finish("no_response");
          return;
        }
      }
      if (pausedAtRef.current === null) {
        setReaction((performance.now() - startedAtRef.current - pausedTotalRef.current) / 1000);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [runState, textOnly, fallbackDurationSeconds, finish]);

  // audio ended -> auto no_response
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || textOnly) return;
    const onEnded = () => finish("no_response");
    audio.addEventListener("ended", onEnded);
    return () => audio.removeEventListener("ended", onEnded);
  }, [finish, textOnly]);

  // tab hidden -> pause audio + timer; resume on visible
  useEffect(() => {
    if (runState !== "playing") return;
    const onVis = () => {
      const audio = audioRef.current;
      if (document.hidden) {
        if (pausedAtRef.current === null) {
          pausedAtRef.current = performance.now();
          setIsPaused(true);
          audio?.pause();
        }
      } else if (pausedAtRef.current !== null) {
        pausedTotalRef.current += performance.now() - pausedAtRef.current;
        pausedAtRef.current = null;
        setIsPaused(false);
        if (!textOnly) void audio?.play().catch(() => setAudioError(true));
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [runState, textOnly]);

  // keyboard: S = scam, R = real, Space = pause/resume (demo shortcuts)
  useEffect(() => {
    if (runState !== "playing") return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const key = e.key.toLowerCase();
      if (key === "s") {
        e.preventDefault();
        finish("identified_scam");
      } else if (key === "r") {
        e.preventDefault();
        finish("fell_for_it");
      } else if (e.code === "Space") {
        e.preventDefault();
        const audio = audioRef.current;
        if (pausedAtRef.current === null) {
          pausedAtRef.current = performance.now();
          setIsPaused(true);
          audio?.pause();
        } else {
          pausedTotalRef.current += performance.now() - pausedAtRef.current;
          pausedAtRef.current = null;
          setIsPaused(false);
          if (!textOnly) void audio?.play().catch(() => setAudioError(true));
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [runState, textOnly, finish]);

  const progressPct = duration > 0 ? Math.min((position / duration) * 100, 100) : 0;

  if (runState === "countdown" || runState === "ringing") {
    return (
      <Cardish>
        <div className="flex flex-col items-center gap-4 py-10 text-center">
          <Phone className="h-10 w-10 animate-pulse text-emerald-400" aria-hidden />
          <div className="font-mono text-6xl font-bold">
            {runState === "countdown" ? countdown : "📞"}
          </div>
          <p className="text-sm text-muted-foreground">
            {runState === "countdown"
              ? "Incoming scam call…"
              : "Ringing… (answer when it connects)"}
          </p>
        </div>
      </Cardish>
    );
  }

  return (
    <Cardish>
      {audioUrl && !audioError && (
        <audio ref={audioRef} src={audioUrl} preload="auto" onError={() => setAudioError(true)} />
      )}

      <div className="flex flex-col items-center gap-1 text-center">
        <Badge variant="outline" className="font-mono text-[10px] uppercase">
          incoming call · unknown number
        </Badge>
        <div className="mt-1 text-lg font-semibold">{scamLabel}</div>
      </div>

      <div className="mt-4 space-y-2">
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={Math.round(progressPct)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-emerald-500 transition-[width] duration-100"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="flex justify-between font-mono text-xs text-muted-foreground">
          <span>{fmt(position)}</span>
          {showStageHints && (
            <span className="text-emerald-400">
              {currentStage ? `stage: ${STAGE_LABELS[currentStage.stage] ?? currentStage.stage}` : "…"}
            </span>
          )}
          <span>{fmt(duration)}</span>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-center gap-2 font-mono text-sm">
        <span className="text-muted-foreground">⏱️ reaction</span>
        <span className="text-2xl font-bold tabular-nums">{reaction.toFixed(1)}s</span>
        {isPaused && <Badge variant="secondary" className="font-mono text-[10px]">paused</Badge>}
      </div>

      {audioError && (
        <p className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-center text-xs text-amber-400">
          Audio could not load — running in text-only mode. The script is timed the same way.
        </p>
      )}

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Button
          variant="destructive"
          size="lg"
          className="h-14 touch-manipulation text-base"
          disabled={!active}
          onClick={() => finish("identified_scam")}
        >
          <ShieldAlert className="mr-2 h-5 w-5" aria-hidden />
          This is a Scam
          <kbd className="ml-2 rounded border border-current px-1 font-mono text-[10px] opacity-70">S</kbd>
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="h-14 touch-manipulation text-base"
          disabled={!active}
          onClick={() => finish("fell_for_it")}
        >
          <ShieldCheck className="mr-2 h-5 w-5" aria-hidden />
          This Seems Real
          <kbd className="ml-2 rounded border border-current px-1 font-mono text-[10px] opacity-70">R</kbd>
        </Button>
      </div>

      {!active && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Ending…
        </div>
      )}

      <p className="mt-4 text-center text-xs text-muted-foreground">
        Tap the moment you&apos;re sure. Hesitation is data — we score the seconds, not the
        shame. <PhoneOff className="inline h-3 w-3" aria-hidden />
      </p>
    </Cardish>
  );
}

function Cardish({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 rounded-xl border border-border/60 bg-card p-5 shadow-lg">
      {children}
    </div>
  );
}
