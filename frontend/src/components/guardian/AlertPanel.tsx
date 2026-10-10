"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Siren, ShieldAlert } from "lucide-react";
import type { AlertLevel } from "@/lib/guardian-ws";

const LEVEL_STYLES: Record<
  Exclude<AlertLevel, "safe">,
  { container: string; icon: typeof AlertTriangle; title: string }
> = {
  suspicious: {
    container: "border-yellow-500/60 bg-yellow-950/40 text-yellow-200",
    icon: ShieldAlert,
    title: "Suspicious call",
  },
  warning: {
    container: "border-orange-500/60 bg-orange-950/40 text-orange-200",
    icon: AlertTriangle,
    title: "Scam likely",
  },
  critical: {
    container: "border-red-500 bg-red-950/50 text-red-100",
    icon: Siren,
    title: "Hang up now",
  },
};

/** Critical alerts fire once: vibrate, notify, beep — then stay on screen. */
function useAlertSideEffects(level: AlertLevel, message: string | null) {
  const lastFired = useRef<string | null>(null);

  useEffect(() => {
    if (level !== "critical" || !message) return;
    const key = message;
    if (lastFired.current === key) return;
    lastFired.current = key;

    try {
      navigator.vibrate?.([200, 100, 200, 100, 200]);
    } catch {
      /* vibration unsupported */
    }

    try {
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        new Notification("🚨 SCAM DETECTED — Hang up now!", { body: message });
      }
    } catch {
      /* notifications unsupported */
    }

    try {
      // Short alarm beep via WebAudio — no asset file needed.
      const Ctx =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (Ctx) {
        const ctx = new Ctx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.value = 880;
        gain.gain.value = 0.08;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
        osc.onended = () => void ctx.close();
      }
    } catch {
      /* audio unsupported */
    }
  }, [level, message]);
}

export function AlertPanel({
  level,
  message,
  signals,
}: {
  level: AlertLevel;
  message: string | null;
  signals: string[];
}) {
  useAlertSideEffects(level, message);

  if (level === "safe" || !message) return null;
  const style = LEVEL_STYLES[level];
  const Icon = style.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={`rounded-lg border p-4 ${style.container}`}
      role="alert"
    >
      {level === "critical" ? (
        <motion.div
          animate={{
            boxShadow: [
              "0 0 0 0 rgba(239, 68, 68, 0)",
              "0 0 0 14px rgba(239, 68, 68, 0.25)",
              "0 0 0 0 rgba(239, 68, 68, 0)",
            ],
          }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="rounded-md"
        >
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 shrink-0" aria-hidden />
            <span className="text-lg font-bold uppercase tracking-wide">
              {style.title}
            </span>
          </div>
        </motion.div>
      ) : (
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 shrink-0" aria-hidden />
          <span className="font-semibold">{style.title}</span>
        </div>
      )}

      <p className="mt-2 text-sm leading-relaxed">{message}</p>

      {signals.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs opacity-90">
          {signals.slice(0, 4).map((signal) => (
            <li key={signal} className="flex gap-2">
              <span aria-hidden>•</span>
              <span>{signal}</span>
            </li>
          ))}
        </ul>
      )}

      {level === "critical" && (
        <p className="mt-3 text-sm font-semibold">
          Do NOT share any OTP, PIN or UPI details.
        </p>
      )}
    </motion.div>
  );
}
