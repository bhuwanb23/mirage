"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, HelpCircle, KeyRound, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export type HandshakeOutcome = "correct" | "couldnt_answer" | "wrong_answer";

interface Challenge {
  question_id: string;
  question: string;
}

interface TotpState {
  code: string;
  expires_in_seconds: number;
}

/** In-call identity challenge (plan §4.6). Shown when stage ≥ urgency or voice > 0.6. */
export function MemoryHandshake({
  familyGroupId,
  relativeLabel = "your family member",
  onOutcome,
  onNeedSetup,
}: {
  familyGroupId: string | null;
  relativeLabel?: string;
  onOutcome: (outcome: HandshakeOutcome) => void;
  onNeedSetup?: () => void;
}) {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [totp, setTotp] = useState<TotpState | null>(null);
  const [typedAnswer, setTypedAnswer] = useState("");
  const [typedCode, setTypedCode] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!familyGroupId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await api.get<{ questions: Challenge[] }>(
          `/memory/questions/${familyGroupId}`,
        );
        if (cancelled) return;
        const questions = data.questions ?? [];
        if (questions.length > 0) {
          const pick = questions[Math.floor(Math.random() * questions.length)];
          setChallenge(pick);
        }
        const current = await api.get<TotpState>(`/memory/totp/${familyGroupId}`);
        if (cancelled) return;
        setTotp(current);
        setError(null);
      } catch {
        if (!cancelled) setError("Could not load your family questions.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [familyGroupId]);

  const verifyTyped = async () => {
    if (!familyGroupId || !challenge || !typedAnswer.trim()) return;
    setBusy(true);
    try {
      const res = await api.post<{ verified: boolean; message: string }>(
        "/memory/verify",
        {
          family_group_id: familyGroupId,
          question_id: challenge.question_id,
          answer: typedAnswer,
        },
      );
      setResult({ ok: res.verified, message: res.message });
      if (res.verified) onOutcome("correct");
      else onOutcome("wrong_answer");
      setTypedAnswer("");
    } catch (err) {
      setError(
        err instanceof Error && "status" in err && err.status === 429
          ? "Too many attempts — locked for 5 minutes."
          : "Verification failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const verifyCode = async () => {
    if (!familyGroupId || !typedCode.trim()) return;
    setBusy(true);
    try {
      const res = await api.post<{ verified: boolean; message: string }>(
        "/memory/verify-totp",
        { family_group_id: familyGroupId, code: typedCode },
      );
      setResult({ ok: res.verified, message: res.message });
      if (res.verified) onOutcome("correct");
      else onOutcome("wrong_answer");
      setTypedCode("");
    } catch {
      setError("Code verification failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  if (!familyGroupId) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          Set up Memory Handshake to verify caller identity. A voice clone
          can&apos;t answer a question only your family knows.
        </p>
        {onNeedSetup && (
          <Button size="sm" onClick={onNeedSetup}>
            <KeyRound className="mr-2 h-4 w-4" aria-hidden />
            Set Up Now
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <KeyRound className="h-4 w-4 text-emerald-400" aria-hidden />
        Identity verification needed
      </div>
      <p className="text-sm text-muted-foreground">
        The caller may not be who they claim. Ask them this question:
      </p>

      <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm font-medium">
        {challenge ? (
          <>“{challenge.question}”</>
        ) : (
          <span className="text-muted-foreground">Loading challenge…</span>
        )}
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            onOutcome("correct");
            setResult({
              ok: true,
              message: `Identity confirmed — but stay alert; a scammer who researched you might know this.`,
            });
          }}
        >
          <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden />
          They answered correctly
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => onOutcome("couldnt_answer")}
        >
          <XCircle className="mr-2 h-4 w-4" aria-hidden />
          They couldn&apos;t answer
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => onOutcome("wrong_answer")}
        >
          <HelpCircle className="mr-2 h-4 w-4" aria-hidden />
          Wrong answer
        </Button>
      </div>

      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Or type what they said:
        </p>
        <div className="flex gap-2">
          <Input
            value={typedAnswer}
            onChange={(e) => setTypedAnswer(e.target.value)}
            placeholder="Their answer…"
            aria-label="Caller's answer"
            onKeyDown={(e) => {
              if (e.key === "Enter") void verifyTyped();
            }}
          />
          <Button size="sm" onClick={() => void verifyTyped()} disabled={busy}>
            Verify
          </Button>
        </div>
      </div>

      <div className="space-y-2 rounded-md border border-border/60 p-3">
        <p className="text-xs font-medium">Or ask for the family code</p>
        {totp && (
          <p className="font-mono text-lg tracking-[0.3em]">
            {totp.code.split("").join(" ")}
            <span className="ml-2 text-xs tracking-normal text-muted-foreground">
              rotates in {totp.expires_in_seconds}s
            </span>
          </p>
        )}
        <div className="flex gap-2">
          <Input
            value={typedCode}
            onChange={(e) => setTypedCode(e.target.value)}
            placeholder="6-digit code"
            inputMode="numeric"
            maxLength={6}
            aria-label="Family code from caller"
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => void verifyCode()}
            disabled={busy}
          >
            Check
          </Button>
        </div>
      </div>

      {result && (
        <div
          className={`rounded-md border p-3 text-sm ${
            result.ok
              ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-200"
              : "border-red-500/60 bg-red-950/40 text-red-200"
          }`}
          role="status"
        >
          {result.ok ? "✅ " : "❌ "}
          {result.message}
        </div>
      )}
      {error && <p className="text-sm text-amber-400">{error}</p>}
      <p className="text-xs text-muted-foreground">
        💡 A real {relativeLabel} will know this. A voice clone or scammer
        will NOT.
      </p>
    </div>
  );
}
