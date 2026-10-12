"use client";

import { useCallback, useEffect, useState } from "react";
import { MemorySetup } from "@/components/guardian/MemorySetup";
import { AlertHistory } from "@/components/family/alert-history";
import { FamilyGroupPanel, InviteBadge } from "@/components/family/family-group-panel";
import { TotpCard } from "@/components/family/totp-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type FamilyStatus } from "@/lib/api";
import { getFamilyGroupId, getUserId, setFamilyGroupId } from "@/lib/auth";
import { notify } from "@/lib/toast";

export default function FamilyPage() {
  const [status, setStatus] = useState<FamilyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [questions, setQuestions] = useState<{ id: string; question: string }[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const userId = getUserId();
      const st = await api.familyStatus(userId, getFamilyGroupId());
      setStatus(st);
      if (st.family_group_id) {
        setFamilyGroupId(st.family_group_id);
        try {
          const q = await api.memoryQuestions(st.family_group_id);
          setQuestions(q.questions ?? []);
        } catch {
          setQuestions([]);
        }
      } else {
        setQuestions([]);
      }
    } catch {
      setStatus(null);
      notify.error("Could not load family status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (loading) {
    return (
      <div className="page-shell space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const linked = Boolean(status?.linked && status.family_group_id);

  return (
    <div className="page-shell space-y-8">
      <header className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-widest text-emerald-400/90">
          Memory handshake
        </p>
        <h1 className="page-title">Family Network</h1>
        <p className="max-w-2xl text-muted-foreground">
          Shared secrets and a rotating family code that voice clones cannot guess.
        </p>
      </header>

      {!linked ? (
        <>
          <div className="rounded-xl border border-dashed border-border/80 bg-card/20 p-6">
            <h2 className="text-lg font-semibold">Get started</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Create or join a family group, then set up at least three Memory Handshake
              questions.
            </p>
          </div>
          <FamilyGroupPanel
            onLinked={() => {
              void refresh();
              setShowSetup(true);
            }}
          />
        </>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-border/60 bg-card/40 p-5 md:col-span-2">
              <h3 className="font-semibold">{status?.name || "Family"}</h3>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Members</dt>
                  <dd className="font-mono text-lg">{status?.member_count ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Handshake</dt>
                  <dd>
                    {status?.handshake_ready ? (
                      <span className="text-emerald-400">Ready</span>
                    ) : (
                      <span className="text-amber-400">Needs setup</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Invite code</dt>
                  <dd className="mt-1">
                    {status?.invite_code ? (
                      <InviteBadge code={status.invite_code} />
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Questions saved</dt>
                  <dd className="font-mono text-lg">{status?.questions_count ?? 0}</dd>
                </div>
              </dl>
              {!status?.handshake_ready ? (
                <Button
                  className="mt-4 min-h-11"
                  onClick={() => setShowSetup(true)}
                >
                  Set up Memory Handshake
                </Button>
              ) : (
                <Button
                  className="mt-4 min-h-11"
                  variant="outline"
                  onClick={() => setShowSetup(true)}
                >
                  Update questions
                </Button>
              )}
            </div>
            {status?.family_group_id && status.has_totp ? (
              <TotpCard familyGroupId={status.family_group_id} />
            ) : (
              <div className="rounded-xl border border-border/60 bg-card/40 p-5 text-sm text-muted-foreground">
                TOTP appears after you save handshake questions.
              </div>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-border/60 bg-card/40 p-5">
              <h3 className="font-semibold">Challenge questions</h3>
              {questions.length === 0 ? (
                <p className="mt-4 text-sm text-muted-foreground">
                  No questions yet. Answers are hashed — never shown again.
                </p>
              ) : (
                <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm">
                  {questions.map((q) => (
                    <li key={q.id}>{q.question}</li>
                  ))}
                </ol>
              )}
            </div>
            <AlertHistory alerts={status?.recent_alerts ?? []} />
          </div>
        </>
      )}

      {showSetup ? (
        <div className="rounded-xl border border-emerald-500/30 bg-card/60 p-4 md:p-6">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">Memory Handshake setup</h2>
            <Button variant="ghost" onClick={() => setShowSetup(false)}>
              Close
            </Button>
          </div>
          <MemorySetup
            onDone={() => {
              notify.success("Memory Handshake saved");
              setShowSetup(false);
              void refresh();
            }}
            onDismiss={() => setShowSetup(false)}
          />
        </div>
      ) : null}
    </div>
  );
}
