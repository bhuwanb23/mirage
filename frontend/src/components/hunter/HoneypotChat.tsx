"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

interface ChatMessage {
  role: "scammer" | "persona";
  text: string;
  tactic?: string;
}

const PERSONAS = [
  { id: "ramesh", label: "Ramesh, 62 — retired bank clerk" },
  { id: "sunita", label: "Sunita Devi, 55 — over-trusting" },
  { id: "vikram", label: "Vikram Singh, 45 — greedy but wary" },
  { id: "meena", label: "Meena Tai, 68 — Marathi-English mix" },
];

const HEALTH_BADGE: Record<string, { label: string; cls: string }> = {
  engaged: { label: "engaged", cls: "bg-emerald-600/20 text-emerald-400" },
  frustrated: { label: "frustrated", cls: "bg-amber-600/20 text-amber-400" },
  about_to_hang_up: { label: "about to hang up", cls: "bg-red-600/20 text-red-400" },
};

/** Split text so known IOC values render as highlighted chips. */
function Highlighted({ text, highlights }: { text: string; highlights: Record<string, string> }) {
  const keys = Object.keys(highlights);
  if (keys.length === 0) return <>{text}</>;
  const escaped = keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(${escaped.join("|")})`, "g");
  const parts = text.split(re);
  return (
    <>
      {parts.map((part, i) =>
        highlights[part] ? (
          <mark
            key={i}
            className="rounded bg-emerald-500/20 px-1 font-mono text-emerald-300"
            title={highlights[part]}
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export default function HoneypotChat({
  onSessionId,
}: {
  onSessionId?: (id: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [highlights, setHighlights] = useState<Record<string, string>>({});
  const [persona, setPersona] = useState("ramesh");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [health, setHealth] = useState("engaged");
  const [totalIocs, setTotalIocs] = useState(0);
  const [timeWasted, setTimeWasted] = useState(0);
  const [tactic, setTactic] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(
    () => () => {
      timers.current.forEach((t) => window.clearTimeout(t));
    },
    [],
  );

  const playScripted = useCallback(async () => {
    setBusy(true);
    try {
      const script = await api.honeypotScripted();
      setMessages([]);
      setHighlights(script.ioc_highlights);
      setSessionId(null);
      onSessionId?.("");
      script.messages.forEach((m, i) => {
        const t = window.setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            { role: m.role === "scammer" ? "scammer" : "persona", text: m.text, tactic: m.tactic },
          ]);
          if (i === script.messages.length - 1) setBusy(false);
        }, 700 * (i + 1));
        timers.current.push(t);
      });
    } catch {
      setBusy(false);
    }
  }, [onSessionId]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "scammer", text }]);
    try {
      const turn = sessionId
        ? await api.honeypotContinue(sessionId, text)
        : await api.honeypotStart(text, persona);
      setSessionId(turn.session_id);
      onSessionId?.(turn.session_id);
      setHealth(turn.conversation_health);
      setTotalIocs(turn.total_iocs_extracted);
      setTimeWasted(turn.estimated_time_wasted_seconds);
      setTactic(turn.tactic_used);
      setMessages((prev) => [
        ...prev,
        { role: "persona", text: turn.reply, tactic: turn.tactic_used },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "persona",
          text: "Sorry beta, my phone is acting up. Can you say that one more time?",
          tactic: "confusion",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }, [busy, input, onSessionId, persona, sessionId]);

  const reset = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    setMessages([]);
    setBusy(false);
    setSessionId(null);
    setTotalIocs(0);
    setTimeWasted(0);
    setTactic(null);
    onSessionId?.("");
  };

  const healthBadge = HEALTH_BADGE[health] ?? HEALTH_BADGE.engaged;

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">Honeypot — bait the scammer</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={`text-[10px] ${healthBadge.cls}`}>
              scammer: {healthBadge.label}
            </Badge>
            <Badge variant="outline" className="font-mono text-[10px]">
              {totalIocs} IOCs · {Math.round(timeWasted / 60)}m wasted
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
          <div className="flex h-[380px] flex-col">
            <div
              ref={scrollRef}
              data-testid="honeypot-scroll"
              className="flex-1 space-y-3 overflow-y-auto rounded-md border border-border/60 bg-zinc-950/60 p-3"
            >
              {messages.length === 0 && (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
                  <span className="text-2xl">🍯</span>
                  <p>
                    Play the scripted demo, or type as the scammer yourself —
                    Ramesh never hangs up and always asks for clarification.
                  </p>
                </div>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.role === "scammer" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                      m.role === "scammer"
                        ? "bg-red-500/10 text-red-100"
                        : "bg-emerald-500/10 text-emerald-50"
                    }`}
                  >
                    <div className="mb-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                      {m.role === "scammer" ? "Scammer" : persona}
                      {m.tactic ? ` · ${m.tactic}` : ""}
                    </div>
                    <Highlighted text={m.text} highlights={highlights} />
                  </div>
                </div>
              ))}
              {busy && messages.length > 0 && (
                <div className="text-xs text-muted-foreground">typing…</div>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <select
                aria-label="Persona"
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                className="h-9 w-[240px] rounded-md border border-border/60 bg-background px-2 text-sm outline-none focus:border-emerald-500/60"
              >
                {PERSONAS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
              <input
                data-testid="scammer-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void send();
                }}
                placeholder="Type as the scammer…"
                className="h-9 flex-1 rounded-md border border-border/60 bg-background px-3 text-sm outline-none focus:border-emerald-500/60"
              />
              <Button size="sm" onClick={() => void send()} disabled={busy || !input.trim()}>
                Send
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void playScripted()}
                disabled={busy}
              >
                Scripted demo
              </Button>
              <Button size="sm" variant="ghost" onClick={reset}>
                Reset
              </Button>
            </div>
          </div>

          {/* Extraction panel */}
          <div className="rounded-md border border-border/60 p-3 text-xs">
            <div className="mb-2 font-medium">Extracted intelligence</div>
            <p className="text-muted-foreground">
              Every message runs through the regex IOC extractor; new IOCs are
              MERGED into the scam graph in real time. Highlighted values in the
              chat are live extractions.
            </p>
            <div className="mt-3 space-y-1 font-mono text-[11px]">
              <div>session: {sessionId ? `${sessionId.slice(0, 12)}…` : "demo (not live)"}</div>
              <div>total IOCs: {totalIocs}</div>
              <div>time wasted: {timeWasted}s</div>
              <div>last tactic: {tactic ?? "—"}</div>
            </div>
            <p className="mt-3 text-muted-foreground">
              After a few turns, the detected ring appears in the graph above —
              shared phone/UPI/domain infrastructure lights up.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
