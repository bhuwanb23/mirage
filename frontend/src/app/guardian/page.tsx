"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, PhoneCall, Play, Send, Square, Radio } from "lucide-react";
import { AlertPanel } from "@/components/guardian/AlertPanel";
import { MemoryHandshake } from "@/components/guardian/MemoryHandshake";
import type { HandshakeOutcome } from "@/components/guardian/MemoryHandshake";
import { MemorySetup, loadFamilyGroupId } from "@/components/guardian/MemorySetup";
import { StageTracker } from "@/components/guardian/StageTracker";
import { TranscriptView } from "@/components/guardian/TranscriptView";
import type { TranscriptLine } from "@/components/guardian/TranscriptView";
import { VoiceAuthenticity } from "@/components/guardian/VoiceAuthenticity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  GuardianSocket,
  type AlertLevel,
  type ConnectionStatus,
  type ReadyMessage,
  type StageUpdateMessage,
  type SummaryMessage,
  type VoiceUpdateMessage,
} from "@/lib/guardian-ws";

const CHUNK_MS = 4000; // 4-second slices (plan §4.1)

/** Pre-rehearsed demo script — walks the 5-stage pipeline (plan §4.6). */
const SCAM_SCRIPT: { label: string; text: string }[] = [
  {
    label: "1 · Hook",
    text: "Hello, is this Priya Sharma? You've been selected for an exclusive reward offer.",
  },
  {
    label: "2 · Authority",
    text: "This is Officer Rajesh from the SBI fraud department, calling about an RBI circular investigation.",
  },
  {
    label: "3 · Isolation",
    text: "Do not tell anyone about this call. This is confidential — don't disconnect and don't inform your family.",
  },
  {
    label: "4 · Urgency",
    text: "Your account will be blocked within 30 minutes. Act immediately, this is your last chance or legal action tonight.",
  },
  {
    label: "5 · Payment",
    text: "Share the OTP and your ATM PIN. Transfer ₹50,000 to this UPI and scan this QR code immediately.",
  },
];

const LEGIT_SCRIPT =
  "Hi mom, I'll be home around 7. Should I pick up bread on the way?";

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

interface OverrideAlert {
  level: AlertLevel;
  message: string;
}

function pickMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported(m));
}

export default function GuardianPage() {
  // --- session state ----------------------------------------------------
  const [mode, setMode] = useState<"audio" | "sim">("sim");
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [running, setRunning] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [stage, setStage] = useState<StageUpdateMessage | null>(null);
  const [voice, setVoice] = useState<VoiceUpdateMessage | null>(null);
  const [simVoice, setSimVoice] = useState<number>(0);
  const [summary, setSummary] = useState<SummaryMessage | null>(null);
  const [skippedNote, setSkippedNote] = useState<string | null>(null);
  const [override, setOverride] = useState<OverrideAlert | null>(null);
  const [handshakeShown, setHandshakeShown] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [bgWarning, setBgWarning] = useState(false);

  // sim input
  const [simText, setSimText] = useState("");

  // memory setup
  const [familyGroupId, setFamilyGroupId] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(false);

  const socketRef = useRef<GuardianSocket | null>(null);
  const stopMicRef = useRef<(() => void) | null>(null);
  const stageRef = useRef<StageUpdateMessage | null>(null);
  const voiceRef = useRef<VoiceUpdateMessage | null>(null);
  const simVoiceRef = useRef(0);

  useEffect(() => {
    // localStorage is an external store — read it after mount (hydration-safe).
    const t = setTimeout(() => setFamilyGroupId(loadFamilyGroupId()), 0);
    return () => clearTimeout(t);
  }, []);

  // --- message handlers -------------------------------------------------
  const handleReady = useCallback((msg: ReadyMessage) => {
    if (!msg.whisper_available && msg.mode === "audio") {
      setSkippedNote(
        "Transcription unavailable (no GROQ key) — use Simulation mode for text.",
      );
    }
  }, []);

  const handleTranscription = useCallback(
    (msg: { text: string; timestamp: string; source: "whisper" | "sim" }) => {
      setLines((prev) => [
        ...prev,
        { timestamp: msg.timestamp, text: msg.text, source: msg.source },
      ]);
    },
    [],
  );

  const handleSkipped = useCallback((msg: { message: string }) => {
    setSkippedNote(msg.message);
  }, []);

  const handleStage = useCallback((msg: StageUpdateMessage) => {
    stageRef.current = msg;
    setStage(msg);
    setElapsed(msg.call_duration_seconds);
    // Trigger the Memory Handshake once per call (plan §4.6).
    if (
      msg.alert_level === "warning" ||
      msg.alert_level === "critical" ||
      ["urgency", "payment"].includes(msg.current_stage)
    ) {
      setHandshakeShown((prev) => {
        if (prev) return prev;
        try {
          navigator.vibrate?.(120);
        } catch {
          /* unsupported */
        }
        return true;
      });
    }
  }, []);

  const handleVoice = useCallback((msg: VoiceUpdateMessage) => {
    voiceRef.current = msg;
    setVoice(msg);
    if (msg.ready && msg.synthetic_score > 0.6) {
      setHandshakeShown((prev) => (prev ? prev : true));
    }
  }, []);

  const handleSummary = useCallback((msg: SummaryMessage) => {
    setSummary(msg);
  }, []);

  const handleError = useCallback((error: string) => {
    setSkippedNote(`Server: ${error}`);
  }, []);

  // --- connection lifecycle --------------------------------------------
  const openSocket = useCallback(
    (m: "audio" | "sim") => {
      const socket = new GuardianSocket(
        {
          onStatus: setStatus,
          onReady: handleReady,
          onTranscription: handleTranscription,
          onTranscriptionSkipped: handleSkipped,
          onStageUpdate: handleStage,
          onVoiceUpdate: handleVoice,
          onSummary: handleSummary,
          onError: handleError,
        },
        m,
      );
      socketRef.current = socket;
      socket.connect();
      if (m === "sim") socket.sendSimVoice(simVoiceRef.current);
      return socket;
    },
    [
      handleReady,
      handleTranscription,
      handleSkipped,
      handleStage,
      handleVoice,
      handleSummary,
      handleError,
    ],
  );

  // --- mic capture: restart loop so every chunk is a complete webm ------
  const startMic = useCallback(
    async (socket: GuardianSocket): Promise<(() => void) | null> => {
      if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
        setMicError(
          "Your browser doesn't support microphone capture. Please use Chrome or Edge.",
        );
        return null;
      }
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } catch {
        setMicError(
          "Microphone access is required for Live Guardian. Please allow microphone access in your browser settings.",
        );
        return null;
      }

      let recorder: MediaRecorder | null = null;
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | null = null;

      const scheduleStop = () => {
        timer = setTimeout(() => {
          if (recorder && recorder.state === "recording") recorder.stop();
        }, CHUNK_MS);
      };

      const start = () => {
        if (stopped) return;
        const mime = pickMime();
        recorder = mime
          ? new MediaRecorder(stream, { mimeType: mime })
          : new MediaRecorder(stream);
        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            void event.data.arrayBuffer().then((buf) => socket.sendAudio(buf));
          }
        };
        recorder.onstop = () => {
          if (!stopped) start(); // fresh recorder → header in every chunk
        };
        recorder.start();
        scheduleStop();
      };
      start();

      return () => {
        stopped = true;
        if (timer) clearTimeout(timer);
        if (recorder && recorder.state === "recording") {
          try {
            recorder.stop();
          } catch {
            /* already stopped */
          }
        }
        stream.getTracks().forEach((track) => track.stop());
      };
    },
    [],
  );

  const start = useCallback(async () => {
    setRunning(true);
    setSummary(null);
    setLines([]);
    setStage(null);
    setVoice(null);
    setOverride(null);
    setHandshakeShown(false);
    setSkippedNote(null);
    setMicError(null);
    setElapsed(0);

    const socket = openSocket(mode);
    if (mode === "audio") {
      const stop = await startMic(socket);
      stopMicRef.current = stop;
      if (!stop) {
        // mic failed — keep the socket so the user still sees status
        setRunning(false);
      }
    }
  }, [mode, openSocket, startMic]);

  const stop = useCallback(() => {
    socketRef.current?.sendEnd(); // summary comes back, then we close
    stopMicRef.current?.();
    stopMicRef.current = null;
    // Give the summary a moment to arrive before tearing down.
    setTimeout(() => {
      socketRef.current?.close();
      socketRef.current = null;
      setRunning(false);
    }, 600);
  }, []);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      stopMicRef.current?.();
      socketRef.current?.close();
    };
  }, []);

  // visibility warning (plan §4.1 edge cases)
  useEffect(() => {
    const onVisibility = () => setBgWarning(document.hidden && running);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [running]);

  // smooth duration ticker while running
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  // --- simulation helpers ----------------------------------------------
  const sendSim = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      socketRef.current?.sendText(text.trim());
      setSimText("");
    },
    [],
  );

  const runScript = useCallback(
    (script: { label: string; text: string }[]) => {
      script.forEach((line, idx) => {
        setTimeout(() => sendSim(line.text), idx * 800);
      });
    },
    [sendSim],
  );

  const changeSimVoice = useCallback((value: number) => {
    setSimVoice(value);
    simVoiceRef.current = value;
    socketRef.current?.sendSimVoice(value);
  }, []);

  // --- handshake outcomes (plan §4.6) ----------------------------------
  const onOutcome = useCallback((outcome: HandshakeOutcome) => {
    if (outcome === "correct") {
      setOverride({
        level: "suspicious",
        message:
          "✅ Identity confirmed — scam confidence reduced. Stay alert anyway.",
      });
    } else if (outcome === "couldnt_answer") {
      setOverride({
        level: "critical",
        message:
          "🚨 CONFIRMED SCAM — a real family member would know this answer. HANG UP NOW.",
      });
    } else {
      setOverride({
        level: "critical",
        message:
          "🚨 WRONG ANSWER — the caller doesn't know your secret. This is almost certainly a scam. HANG UP NOW.",
      });
    }
    try {
      navigator.vibrate?.([300, 150, 300]);
    } catch {
      /* unsupported */
    }
  }, []);

  // --- derived state -----------------------------------------------------
  const effectiveAlert: { level: AlertLevel; message: string | null } = override
    ? { level: override.level, message: override.message }
    : {
        level: stage?.alert_level ?? "safe",
        message: stage?.alert_message ?? null,
      };

  const statusBadge: Record<ConnectionStatus, string> = {
    idle: "Idle",
    connecting: "Connecting…",
    open: "Connected",
    reconnecting: "🔄 Reconnecting…",
    closed: "Disconnected",
  };

  // Call summary view (plan §4.3 edge case: freeze + summary on Stop).
  if (summary) {
    const minutes = Math.floor(summary.duration_seconds / 60);
    const seconds = Math.floor(summary.duration_seconds % 60);
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PhoneCall className="h-5 w-5 text-emerald-400" aria-hidden />
              Call ended
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Stat label="Duration" value={`${minutes}:${String(seconds).padStart(2, "0")}`} />
              <Stat label="Highest stage" value={summary.highest_stage.toUpperCase()} />
              <Stat label="Alert" value={summary.peak_alert_level.toUpperCase()} />
              <Stat
                label="Voice AI"
                value={`${Math.round(summary.voice_score * 100)}%`}
              />
            </div>
            <div
              className={`rounded-md border p-3 text-sm ${
                summary.is_scam_likely
                  ? "border-red-500/60 bg-red-950/40"
                  : "border-emerald-500/60 bg-emerald-500/10"
              }`}
            >
              {summary.verdict}
            </div>
            <p className="text-xs text-muted-foreground">
              {summary.chunks_classified} chunks classified
              {summary.llm_classifications > 0 &&
                ` · ${summary.llm_classifications} via LLM`}{" "}
              · voice score {Math.round(summary.voice_score * 100)}%
            </p>
            <Button
              onClick={() => {
                setSummary(null);
                setStage(null);
                setLines([]);
                setOverride(null);
              }}
            >
              New call
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <PhoneCall className="h-6 w-6 text-emerald-400" aria-hidden />
          <h1 className="text-2xl font-bold tracking-tight">Live Call Guardian</h1>
          <Badge variant="outline" className="font-mono text-[10px]">
            Phase 4
          </Badge>
          <Badge variant="secondary" className="font-mono text-[10px]">
            {statusBadge[status]}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          {!running ? (
            <>
              <div className="flex rounded-md border border-border/60 p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setMode("sim")}
                  className={`rounded px-3 py-1.5 ${mode === "sim" ? "bg-accent" : "text-muted-foreground"}`}
                >
                  Simulation
                </button>
                <button
                  type="button"
                  onClick={() => setMode("audio")}
                  className={`rounded px-3 py-1.5 ${mode === "audio" ? "bg-accent" : "text-muted-foreground"}`}
                >
                  Live mic
                </button>
              </div>
              <Button onClick={() => void start()}>
                {mode === "audio" ? (
                  <Mic className="mr-2 h-4 w-4" aria-hidden />
                ) : (
                  <Play className="mr-2 h-4 w-4" aria-hidden />
                )}
                Start Listening
              </Button>
            </>
          ) : (
            <Button variant="destructive" onClick={stop}>
              <Square className="mr-2 h-4 w-4" aria-hidden />
              Stop
            </Button>
          )}
        </div>
      </div>

      <p className="mt-2 text-sm text-muted-foreground">
        {mode === "audio"
          ? "Mic audio streams in 4-second chunks → Whisper → stage classifier. Keep this tab active."
          : "Simulation mode — send scripted lines to watch the pipeline classify stages live, no mic needed."}
      </p>

      {bgWarning && (
        <p className="mt-2 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          ⚠️ Keep this tab active for real-time monitoring.
        </p>
      )}
      {micError && (
        <p className="mt-2 rounded-md border border-red-500/50 bg-red-950/40 px-3 py-2 text-xs text-red-300">
          {micError}
        </p>
      )}
      {skippedNote && (
        <p className="mt-2 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          ⚠️ {skippedNote}
        </p>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        {/* Left column — transcript + alert */}
        <div className="space-y-4 lg:col-span-3">
          <Card className="border-border/60">
            <CardContent className="pt-6">
              <TranscriptView
                lines={lines}
                emptyHint={
                  running
                    ? mode === "audio"
                      ? "Listening… speech will appear here within ~5–7 s."
                      : "Send a scripted line to begin."
                    : "Press Start Listening to open the pipeline."
                }
              />
            </CardContent>
          </Card>

          <AlertPanel
            level={effectiveAlert.level}
            message={effectiveAlert.message}
            signals={stage?.signals ?? []}
          />

          {running && mode === "sim" && (
            <Card className="border-border/60">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Radio className="h-4 w-4 text-emerald-400" aria-hidden />
                  Simulation controls
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input
                    value={simText}
                    onChange={(e) => setSimText(e.target.value)}
                    placeholder="Type what the caller says…"
                    aria-label="Simulated caller speech"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") sendSim(simText);
                    }}
                  />
                  <Button size="sm" onClick={() => sendSim(simText)}>
                    <Send className="h-4 w-4" aria-hidden />
                  </Button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {SCAM_SCRIPT.map((line) => (
                    <Button
                      key={line.label}
                      size="sm"
                      variant="outline"
                      className="text-[11px]"
                      onClick={() => sendSim(line.text)}
                    >
                      {line.label}
                    </Button>
                  ))}
                  <Button
                    size="sm"
                    variant="secondary"
                    className="text-[11px]"
                    onClick={() => runScript(SCAM_SCRIPT)}
                  >
                    ▶ Run full scam script
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-[11px]"
                    onClick={() => sendSim(LEGIT_SCRIPT)}
                  >
                    Legit call
                  </Button>
                </div>

                <div className="space-y-1">
                  <label
                    htmlFor="sim-voice"
                    className="flex items-center justify-between text-xs text-muted-foreground"
                  >
                    <span>Simulated voice score</span>
                    <span className="font-mono">{Math.round(simVoice * 100)}% AI</span>
                  </label>
                  <input
                    id="sim-voice"
                    type="range"
                    min={0}
                    max={100}
                    value={Math.round(simVoice * 100)}
                    onChange={(e) => changeSimVoice(Number(e.target.value) / 100)}
                    className="w-full accent-emerald-500"
                  />
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right column — tracker, voice, handshake */}
        <div className="space-y-4 lg:col-span-2">
          <Card className="border-border/60">
            <CardContent className="pt-6">
              <StageTracker
                currentStage={stage?.current_stage ?? "none"}
                confidence={stage?.confidence ?? 0}
                alertLevel={stage?.alert_level ?? "safe"}
                durationSeconds={elapsed}
                stageTimestamps={stage?.stage_timestamps ?? {}}
              />
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardContent className="pt-6">
              <VoiceAuthenticity
                voice={voice}
                simulatedScore={mode === "sim" ? simVoice : undefined}
              />
            </CardContent>
          </Card>

          {handshakeShown && !override && (
            <Card className="border-emerald-500/40">
              <CardContent className="pt-6">
                <MemoryHandshake
                  familyGroupId={familyGroupId}
                  onOutcome={onOutcome}
                  onNeedSetup={() => setShowSetup(true)}
                />
              </CardContent>
            </Card>
          )}

          {(showSetup || (!familyGroupId && running && handshakeShown)) && (
            <Card className="border-border/60">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Memory Handshake setup</CardTitle>
              </CardHeader>
              <CardContent>
                <MemorySetup
                  onDone={(id) => {
                    setFamilyGroupId(id);
                    // Keep the card open so the user sees the invite code
                    // and TOTP secret to share with family (Done dismisses).
                  }}
                  onDismiss={() => setShowSetup(false)}
                />
              </CardContent>
            </Card>
          )}

          {!familyGroupId && !showSetup && (
            <div className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2 text-sm">
              <span className="text-muted-foreground">
                🔐 Memory Handshake not set up
              </span>
              <Button size="sm" variant="outline" onClick={() => setShowSetup(true)}>
                Set up
              </Button>
            </div>
          )}
        </div>
      </div>

      <Separator className="my-6" />
      <p className="text-xs text-muted-foreground">
        Tip: use speakerphone or earbuds for better separation. Never share
        OTP, PIN or UPI details with anyone — no bank or officer will ever
        ask for them.
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/60 p-3">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="font-mono text-lg">{value}</div>
    </div>
  );
}
