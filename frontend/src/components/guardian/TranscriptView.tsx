"use client";

import { useEffect, useRef } from "react";

export interface TranscriptLine {
  timestamp: string;
  text: string;
  source: "whisper" | "sim";
}

/** Scam keywords highlighted in red (plan §4.3 TranscriptView). */
const HIGHLIGHTS = [
  "otp",
  "pin",
  "transfer",
  "blocked",
  "immediately",
  "urgent",
  "qr code",
  "rupees",
  "upi",
  "suspend",
  "frozen",
  "deadline",
  "last chance",
];

function highlight(text: string): React.ReactNode[] {
  const pattern = new RegExp(`(${HIGHLIGHTS.join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    HIGHLIGHTS.some((h) => h.toLowerCase() === part.toLowerCase()) ? (
      <mark
        key={i}
        className="rounded bg-red-500/20 px-0.5 font-semibold text-red-300"
      >
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

export function TranscriptView({
  lines,
  emptyHint,
}: {
  lines: TranscriptLine[];
  emptyHint: string;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines.length]);

  return (
    <div className="flex h-full min-h-64 flex-col">
      <div className="flex items-center justify-between border-b border-border/60 pb-2">
        <span className="text-sm font-medium">Live transcript</span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {lines.length} segments
        </span>
      </div>

      <div className="mt-2 max-h-80 flex-1 space-y-2 overflow-y-auto pr-1">
        {lines.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {emptyHint}
          </p>
        ) : (
          lines.map((line, idx) => (
            <div key={idx} className="flex gap-2 text-sm leading-relaxed">
              <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                {line.timestamp}
              </span>
              <span className={line.source === "sim" ? "text-foreground" : "text-foreground/90"}>
                {highlight(line.text)}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
