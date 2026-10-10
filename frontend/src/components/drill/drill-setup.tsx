"use client";

import { useState } from "react";
import { Loader2, Upload } from "lucide-react";
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
import { LANGUAGES } from "@/lib/constants";
import { BANK_OPTIONS, type ScamTypeInfo } from "@/lib/drill-api";

export interface DrillFormValues {
  name: string;
  city: string;
  bank: string;
  employer: string;
  relativeName: string;
  relativeRelation: string;
  language: string;
  scamType: string;
  difficulty: string;
  voiceFile: File | null;
}

const DIFFICULTIES = [
  { id: "easy", label: "Easy", hint: "Obvious red flags" },
  { id: "medium", label: "Medium", hint: "Realistic pressure" },
  { id: "hard", label: "Hard", hint: "Subtle, no stage hints" },
] as const;

const MAX_VOICE_BYTES = 5 * 1024 * 1024; // matches backend limit

export function DrillSetup({
  scamTypes,
  initial,
  busy,
  error,
  onSubmit,
}: {
  scamTypes: ScamTypeInfo[];
  initial?: Partial<DrillFormValues>;
  busy: boolean;
  error: string | null;
  onSubmit: (values: DrillFormValues) => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [city, setCity] = useState(initial?.city ?? "");
  const [bank, setBank] = useState(initial?.bank ?? "sbi");
  const [employer, setEmployer] = useState(initial?.employer ?? "");
  const [relativeName, setRelativeName] = useState(initial?.relativeName ?? "");
  const [relativeRelation, setRelativeRelation] = useState(
    initial?.relativeRelation ?? "",
  );
  const [language, setLanguage] = useState(initial?.language ?? LANGUAGES[0].id);
  const [scamType, setScamType] = useState(
    initial?.scamType ?? scamTypes[0]?.id ?? "bank_kyc",
  );
  const [difficulty, setDifficulty] = useState(
    initial?.difficulty ?? scamTypes.find((t) => t.id === scamType)?.default_difficulty ?? "medium",
  );
  const [voiceFile, setVoiceFile] = useState<File | null>(initial?.voiceFile ?? null);
  const [voiceWarning, setVoiceWarning] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const pickScam = (id: string) => {
    setScamType(id);
    const def = scamTypes.find((t) => t.id === id)?.default_difficulty;
    if (def) setDifficulty(def);
  };

  const onFile = (file: File | null) => {
    setVoiceWarning(null);
    if (!file) {
      setVoiceFile(null);
      return;
    }
    if (file.size > MAX_VOICE_BYTES) {
      setVoiceWarning("Clip too large (max 5 MB). Try a shorter recording.");
      return;
    }
    setVoiceFile(file);
  };

  const submit = () => {
    if (!name.trim()) {
      setFormError("Name is required — the scammer will use it.");
      return;
    }
    setFormError(null);
    onSubmit({
      name: name.trim(),
      city: city.trim(),
      bank,
      employer: employer.trim(),
      relativeName: relativeName.trim(),
      relativeRelation: relativeRelation.trim(),
      language,
      scamType,
      difficulty,
      voiceFile,
    });
  };

  return (
    <Card className="mt-6 border-border/60">
      <CardHeader>
        <CardTitle>Configure the drill</CardTitle>
        <CardDescription>
          The script is personalized with these details — use your real ones, that&apos;s
          the point. Nothing leaves your machine without a backend you control.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="drill-name">
              Your name <span className="text-red-400">*</span>
            </label>
            <Input
              id="drill-name"
              placeholder="e.g. Priya Sharma"
              value={name}
              disabled={busy}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="drill-city">
              City
            </label>
            <Input
              id="drill-city"
              placeholder="e.g. Mumbai"
              value={city}
              disabled={busy}
              onChange={(e) => setCity(e.target.value)}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="drill-bank">
              Primary bank
            </label>
            <select
              id="drill-bank"
              value={bank}
              disabled={busy}
              onChange={(e) => setBank(e.target.value)}
              className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm dark:bg-input/30"
            >
              {BANK_OPTIONS.map((b) => (
                <option key={b.id} value={b.id} className="bg-background text-foreground">
                  {b.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="drill-employer">
              Workplace <span className="text-xs text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="drill-employer"
              placeholder="e.g. TCS"
              value={employer}
              disabled={busy}
              onChange={(e) => setEmployer(e.target.value)}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="drill-relative">
              Relative&apos;s name{" "}
              <span className="text-xs text-muted-foreground">(for distress scams)</span>
            </label>
            <Input
              id="drill-relative"
              placeholder="e.g. Aarav"
              value={relativeName}
              disabled={busy}
              onChange={(e) => setRelativeName(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="drill-relation">
              Their relation to you
            </label>
            <Input
              id="drill-relation"
              placeholder="e.g. son"
              value={relativeRelation}
              disabled={busy}
              onChange={(e) => setRelativeRelation(e.target.value)}
            />
          </div>
        </div>

        <Separator />

        <div>
          <span className="mb-2 block text-sm font-medium">Scam type</span>
          <div className="flex flex-wrap gap-2">
            {scamTypes.map((t) => (
              <Button
                key={t.id}
                size="sm"
                variant={scamType === t.id ? "default" : "outline"}
                disabled={busy}
                onClick={() => pickScam(t.id)}
              >
                {t.label}
              </Button>
            ))}
          </div>
        </div>

        <div>
          <span className="mb-2 block text-sm font-medium">Difficulty</span>
          <div className="flex flex-wrap gap-2">
            {DIFFICULTIES.map((d) => (
              <Button
                key={d.id}
                size="sm"
                variant={difficulty === d.id ? "default" : "outline"}
                disabled={busy}
                onClick={() => setDifficulty(d.id)}
                title={d.hint}
              >
                {d.label}
              </Button>
            ))}
          </div>
          {(() => {
            const est = scamTypes.find((t) => t.id === scamType)?.estimated_duration_seconds;
            if (!est) return null;
            return (
              <p className="mt-2 text-xs text-muted-foreground">
                ≈ {Math.round(est)}-second call · 5 manipulation stages · answer when
                it rings
              </p>
            );
          })()}
        </div>

        <div>
          <span className="mb-2 block text-sm font-medium">Language</span>
          <div className="flex flex-wrap gap-2">
            {LANGUAGES.map((l) => (
              <Button
                key={l.id}
                size="sm"
                variant={language === l.id ? "default" : "outline"}
                disabled={busy}
                onClick={() => setLanguage(l.id)}
              >
                {l.label}
              </Button>
            ))}
          </div>
        </div>

        <div>
          <span className="mb-2 block text-sm font-medium">
            Voice clip{" "}
            <Badge variant="outline" className="font-mono text-[10px]">
              optional
            </Badge>
          </span>
          <p className="mt-1 text-xs text-muted-foreground">
            5–60 seconds of clear speech, used only for voice-cloning experiments. Skip it
            and a standard scammer voice is used.
          </p>
          <label
            className="mt-2 flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border/80 px-3 py-2 text-sm text-muted-foreground hover:border-emerald-500/50 hover:text-foreground"
            htmlFor="drill-voice"
          >
            <Upload className="h-4 w-4" aria-hidden />
            {voiceFile ? voiceFile.name : "Choose .wav / .mp3 / .m4a / .ogg"}
            <input
              id="drill-voice"
              type="file"
              accept=".wav,.mp3,.m4a,.ogg,audio/*"
              className="sr-only"
              disabled={busy}
              onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {voiceWarning && <p className="mt-1 text-xs text-amber-400">{voiceWarning}</p>}
        </div>

        {(formError || error) && (
          <p className="text-sm text-red-400" role="alert">
            {formError ?? error}
          </p>
        )}

        <Separator />
        <Button onClick={submit} disabled={busy} className="w-full" size="lg">
          {busy ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              Writing the scam script…
            </>
          ) : (
            "Arm the drill"
          )}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          ⚠️ This is a simulation. No real scam is being attempted. Your data is safe.
        </p>
      </CardContent>
    </Card>
  );
}
