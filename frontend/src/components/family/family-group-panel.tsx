"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { getUserId, setFamilyGroupId } from "@/lib/auth";
import { notify } from "@/lib/toast";

export function FamilyGroupPanel({
  onLinked,
}: {
  onLinked: (groupId: string, invite: string) => void;
}) {
  const [name, setName] = useState("Family");
  const [joinCode, setJoinCode] = useState("");
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    try {
      const res = await api.createFamilyGroup(name.trim() || "Family", getUserId());
      setFamilyGroupId(res.family_group_id);
      notify.success("Family group created");
      onLinked(res.family_group_id, res.invite_code);
    } catch {
      notify.error("Could not create family group");
    } finally {
      setBusy(false);
    }
  };

  const join = async () => {
    if (!joinCode.trim()) return;
    setBusy(true);
    try {
      const res = await api.joinFamilyGroup(joinCode.trim(), getUserId());
      setFamilyGroupId(res.family_group_id);
      notify.success("Joined family group");
      onLinked(res.family_group_id, res.invite_code);
    } catch {
      notify.error("Invalid invite code");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="rounded-xl border border-border/60 bg-card/40 p-5">
        <h3 className="font-semibold">Create a group</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Share the invite code with family so they can join.
        </p>
        <Input
          className="mt-4"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Group name"
          aria-label="Group name"
        />
        <Button className="mt-3 min-h-11" disabled={busy} onClick={() => void create()}>
          Create group
        </Button>
      </div>
      <div className="rounded-xl border border-border/60 bg-card/40 p-5">
        <h3 className="font-semibold">Join with invite code</h3>
        <p className="mt-1 text-sm text-muted-foreground">Format like ABC-123.</p>
        <Input
          className="mt-4 font-mono uppercase"
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value)}
          placeholder="ABC-123"
          aria-label="Invite code"
        />
        <Button
          className="mt-3 min-h-11"
          variant="outline"
          disabled={busy || !joinCode.trim()}
          onClick={() => void join()}
        >
          Join group
        </Button>
      </div>
    </div>
  );
}

export function InviteBadge({ code }: { code: string }) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-2 rounded-md border border-border/60 bg-muted/40 px-3 py-1.5 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={async () => {
        await navigator.clipboard.writeText(code);
        notify.success("Invite code copied");
      }}
      aria-label={`Copy invite code ${code}`}
    >
      {code}
      <Copy className="h-3.5 w-3.5" aria-hidden />
    </button>
  );
}
