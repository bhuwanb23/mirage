"use client";

import { useState } from "react";
import { Copy, KeyRound, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

const STORAGE_KEY = "mirage_family_group";

export function loadFamilyGroupId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export function saveFamilyGroupId(groupId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, groupId);
}

interface QuestionDraft {
  question: string;
  answer: string;
}

const EMPTY: QuestionDraft[] = [
  { question: "", answer: "" },
  { question: "", answer: "" },
  { question: "", answer: "" },
];

/** Setup flow: create/join group → 3 shared secrets → invite code + TOTP secret. */
export function MemorySetup({
  onDone,
  onDismiss,
}: {
  onDone: (familyGroupId: string) => void;
  /** Called when the user closes the post-save confirmation panel. */
  onDismiss?: () => void;
}) {
  const [step, setStep] = useState<"group" | "questions">("group");
  const [groupId, setGroupId] = useState<string | null>(null);
  const [inviteCode, setInviteCode] = useState<string>("");
  const [joinCode, setJoinCode] = useState("");
  const [drafts, setDrafts] = useState<QuestionDraft[]>(EMPTY);
  const [saved, setSaved] = useState<{ totp_secret: string; invite: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const createGroup = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ family_group_id: string; invite_code: string }>(
        "/memory/group",
        { name: "Family" },
      );
      setGroupId(res.family_group_id);
      setInviteCode(res.invite_code);
      setStep("questions");
    } catch {
      setError("Could not create a family group. Is the backend running?");
    } finally {
      setBusy(false);
    }
  };

  const joinGroup = async () => {
    if (!joinCode.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ family_group_id: string; invite_code: string }>(
        "/memory/group/join",
        { invite_code: joinCode.trim() },
      );
      setGroupId(res.family_group_id);
      setInviteCode(res.invite_code);
      setStep("questions");
    } catch {
      setError("Invalid invite code.");
    } finally {
      setBusy(false);
    }
  };

  const updateDraft = (idx: number, field: keyof QuestionDraft, value: string) => {
    setDrafts((prev) => prev.map((d, i) => (i === idx ? { ...d, [field]: value } : d)));
  };

  const saveQuestions = async () => {
    if (!groupId) return;
    if (drafts.some((d) => !d.question.trim() || !d.answer.trim())) {
      setError("Every question needs an answer.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{
        status: string;
        questions_count: number;
        totp_secret: string;
        message: string;
      }>("/memory/setup", {
        family_group_id: groupId,
        questions: drafts.map((d) => ({
          question: d.question.trim(),
          answer: d.answer.trim(),
        })),
      });
      setSaved({ totp_secret: res.totp_secret, invite: inviteCode });
      saveFamilyGroupId(groupId);
      onDone(groupId);
    } catch (err) {
      setError(
        err instanceof Error && "status" in err && err.status === 400
          ? "Please add at least 3 questions."
          : "Could not save questions.",
      );
    } finally {
      setBusy(false);
    }
  };

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  if (step === "group") {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Users className="h-4 w-4 text-emerald-400" aria-hidden />
          Family group
        </div>
        <p className="text-sm text-muted-foreground">
          Create a group and invite your family with the code — everyone in
          the group shares the same secret questions.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button size="sm" onClick={() => void createGroup()} disabled={busy}>
            Create family group
          </Button>
          <div className="flex gap-2">
            <Input
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value)}
              placeholder="ABC-123"
              aria-label="Invite code to join"
              className="w-32 font-mono uppercase"
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={() => void joinGroup()}
              disabled={busy || !joinCode.trim()}
            >
              Join
            </Button>
          </div>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>
    );
  }

  if (saved) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-emerald-300">
          <KeyRound className="h-4 w-4" aria-hidden />
          Memory Handshake configured
        </div>
        <div className="flex items-center gap-2 rounded-md border border-border/60 p-3 text-sm">
          <span className="font-mono text-lg tracking-widest">{saved.invite}</span>
          <Button size="sm" variant="ghost" onClick={() => void copyInvite()}>
            <Copy className="h-4 w-4" aria-hidden />
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          TOTP secret: <span className="font-mono">{saved.totp_secret}</span> —
          share it with family so they can read the rotating family code.
        </p>
        {onDismiss && (
          <Button size="sm" onClick={onDismiss}>
            Done
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="h-4 w-4 text-emerald-400" aria-hidden />
          Secret questions
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          invite {inviteCode}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        ⚠️ Choose questions a scammer couldn&apos;t find on social media.
        Answers are stored as hashes — never plain text.
      </p>

      <div className="space-y-3">
        {drafts.map((draft, idx) => (
          <div key={idx} className="space-y-2">
            <Input
              value={draft.question}
              onChange={(e) => updateDraft(idx, "question", e.target.value)}
              placeholder={`Question ${idx + 1} — e.g. What did we name our dog in 2019?`}
              aria-label={`Secret question ${idx + 1}`}
            />
            <Input
              value={draft.answer}
              onChange={(e) => updateDraft(idx, "answer", e.target.value)}
              placeholder={`Answer ${idx + 1}`}
              aria-label={`Secret answer ${idx + 1}`}
            />
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex gap-3">
        <Button size="sm" onClick={() => void saveQuestions()} disabled={busy}>
          Save secrets
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setStep("group")}>
          Back
        </Button>
      </div>
    </div>
  );
}
