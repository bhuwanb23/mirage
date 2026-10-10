import { API_URL } from "./constants";

/** Server → client message contracts (mirrors backend/app/routers/guardian.py). */

export type AlertLevel = "safe" | "suspicious" | "warning" | "critical";
export type ScamStage =
  | "none"
  | "hook"
  | "authority"
  | "isolation"
  | "urgency"
  | "payment";
export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed";

export interface ReadyMessage {
  type: "ready";
  session_id: string;
  mode: "audio" | "sim";
  language: string;
  whisper_available: boolean;
  voice_method: string;
  llm_providers: string[];
  scam_keywords: string[];
}

export interface TranscriptionMessage {
  type: "transcription";
  chunk_id: number;
  text: string;
  timestamp: string;
  source: "whisper" | "sim";
  transcript_so_far: string;
}

export interface TranscriptionSkippedMessage {
  type: "transcription_skipped";
  chunk_id: number;
  reason: string;
  message: string;
}

export interface StageUpdateMessage {
  type: "stage_update";
  current_stage: ScamStage;
  previous_stage: ScamStage;
  confidence: number;
  alert_level: AlertLevel;
  alert_message: string | null;
  signals: string[];
  transcript_so_far: string;
  call_duration_seconds: number;
  stage_timestamps: Record<string, number | null>;
  is_scam_likely: boolean;
  classification_source: string;
}

export interface VoiceUpdateMessage {
  type: "voice_update";
  synthetic_score: number;
  label: string;
  intra_chunk_similarity: number | null;
  inter_chunk_similarity: number | null;
  reference_match: number | null;
  chunks_analyzed: number;
  ready: boolean;
  available: boolean;
  method: string;
  quality_warning: string | null;
}

export interface SummaryMessage {
  type: "summary";
  duration_seconds: number;
  highest_stage: ScamStage;
  final_stage: ScamStage;
  peak_alert_level: AlertLevel;
  confidence: number;
  is_scam_likely: boolean;
  verdict: string;
  chunks_classified: number;
  llm_classifications: number;
  transcript: string;
  stage_timestamps: Record<string, number | null>;
  chunks: number;
  voice_score: number;
  mode: string;
}

export interface GuardianHandlers {
  onStatus?: (status: ConnectionStatus) => void;
  onReady?: (msg: ReadyMessage) => void;
  onTranscription?: (msg: TranscriptionMessage) => void;
  onTranscriptionSkipped?: (msg: TranscriptionSkippedMessage) => void;
  onStageUpdate?: (msg: StageUpdateMessage) => void;
  onVoiceUpdate?: (msg: VoiceUpdateMessage) => void;
  onSummary?: (msg: SummaryMessage) => void;
  onError?: (error: string) => void;
}

function guardianUrl(): string {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}/guardian/stream`;
}

const HEARTBEAT_MS = 30_000; // Render kills idle sockets
const MAX_BACKOFF_MS = 10_000;

/**
 * WebSocket manager for the Live Guardian.
 *
 * - sends `init` on open
 * - heartbeat ping every 30 s
 * - auto-reconnect with exponential backoff (1s → 2s → 4s → max 10s),
 *   re-sending `init` with the same session_id so the backend keeps one
 *   session across brief drops
 * - `end()` opts out of reconnection (user pressed Stop)
 */
export class GuardianSocket {
  private ws: WebSocket | null = null;
  private handlers: GuardianHandlers;
  private mode: "audio" | "sim";
  private language: string;
  private sessionId: string;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private backoff = 1000;
  private manuallyClosed = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private status: ConnectionStatus = "idle";

  constructor(handlers: GuardianHandlers, mode: "audio" | "sim" = "audio", language = "auto") {
    this.handlers = handlers;
    this.mode = mode;
    this.language = language;
    this.sessionId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  get sessionIdValue(): string {
    return this.sessionId;
  }

  private setStatus(status: ConnectionStatus) {
    this.status = status;
    this.handlers.onStatus?.(status);
  }

  connect(): void {
    this.manuallyClosed = false;
    this.setStatus(this.status === "open" ? "open" : "connecting");
    const ws = new WebSocket(guardianUrl());
    ws.binaryType = "arraybuffer";
    this.ws = ws;

    ws.onopen = () => {
      this.backoff = 1000;
      ws.send(
        JSON.stringify({
          type: "init",
          session_id: this.sessionId,
          language: this.language,
          mode: this.mode,
        }),
      );
      this.setStatus("open");
      this.startHeartbeat();
    };

    ws.onmessage = (event) => this.dispatch(event.data);

    ws.onerror = () => {
      // onclose fires right after; reconnection is handled there.
    };

    ws.onclose = () => {
      this.stopHeartbeat();
      if (this.manuallyClosed) {
        this.setStatus("closed");
        return;
      }
      this.setStatus("reconnecting");
      this.scheduleReconnect();
    };
  }

  private dispatch(data: unknown): void {
    if (typeof data !== "string") return;
    let msg: { type?: string };
    try {
      msg = JSON.parse(data);
    } catch {
      return;
    }
    switch (msg.type) {
      case "ready":
        this.handlers.onReady?.(msg as ReadyMessage);
        break;
      case "transcription":
        this.handlers.onTranscription?.(msg as TranscriptionMessage);
        break;
      case "transcription_skipped":
        this.handlers.onTranscriptionSkipped?.(msg as TranscriptionSkippedMessage);
        break;
      case "stage_update":
        this.handlers.onStageUpdate?.(msg as StageUpdateMessage);
        break;
      case "voice_update":
        this.handlers.onVoiceUpdate?.(msg as VoiceUpdateMessage);
        break;
      case "summary":
        this.handlers.onSummary?.(msg as SummaryMessage);
        break;
      case "error":
        this.handlers.onError?.(
          (msg as { error?: string }).error ?? "unknown server error",
        );
        break;
      case "pong":
        break;
      default:
        break;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeat = setInterval(() => {
      this.rawSend({ type: "ping" });
    }, HEARTBEAT_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeat) {
      clearInterval(this.heartbeat);
      this.heartbeat = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const delay = this.backoff;
    this.backoff = Math.min(this.backoff * 2, MAX_BACKOFF_MS);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.manuallyClosed) this.connect();
    }, delay);
  }

  private rawSend(payload: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  /** Binary audio chunk (4 s webm/opus from MediaRecorder). */
  sendAudio(chunk: ArrayBuffer): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(chunk);
    }
  }

  /** Simulation mode: text stands in for a transcribed chunk. */
  sendText(text: string): void {
    this.rawSend({ type: "text", text });
  }

  /** Simulation mode: inject a synthetic-voice score (0..1). */
  sendSimVoice(score: number): void {
    this.rawSend({ type: "sim_voice", score });
  }

  /** Graceful stop — server replies with the call summary. */
  sendEnd(): void {
    this.rawSend({ type: "end" });
  }

  /** Stop for good (no auto-reconnect). */
  close(): void {
    this.manuallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopHeartbeat();
    this.ws?.close();
    this.ws = null;
    this.setStatus("closed");
  }
}
