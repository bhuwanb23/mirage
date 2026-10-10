import { API_URL } from "./constants";
import { ApiError, api } from "./api";

// ---------------------------------------------------------------------------
// Types — mirror backend/app/models/schemas.py
// ---------------------------------------------------------------------------

export interface DrillProfileRequest {
  name: string;
  city?: string;
  bank?: string;
  employer?: string;
  relative_name?: string;
  relative_relation?: string;
  language: string;
  user_id?: string;
}

export interface DrillProfileOut {
  profile_id: string;
  user_id: string;
  name: string;
  first_name: string;
  city: string;
  bank: string;
  bank_full_name: string;
  employer: string | null;
  relative_name: string | null;
  relative_relation: string | null;
  language: string;
  voice_clip_url: string | null;
  voice_duration_seconds: number;
  status: string;
  message: string;
}

export interface DrillStage {
  stage: string;
  order: number;
  timestamp_hint: string;
  start_seconds: number;
  end_seconds: number;
  script: string;
  tactic: string;
}

export interface DrillScriptOut {
  script_id: string;
  profile_id: string;
  scam_type: string;
  title: string;
  full_script: string;
  stages: DrillStage[];
  red_flags_planted: string[];
  difficulty_level: string;
  estimated_duration_seconds: number;
  language: string;
  source: string;
}

export interface DrillSynthesizeOut {
  script_id: string;
  audio_url: string | null;
  duration_seconds: number;
  method_used: string;
  status: string;
  message: string;
}

export interface DebriefStageDetail {
  stage: string;
  timestamp: string;
  what_happened: string;
  why_it_works: string;
  real_world_tip: string;
}

export interface DrillDebrief {
  outcome: string;
  headline: string;
  reaction_assessment: string;
  stages_caught: DebriefStageDetail[];
  stages_missed: DebriefStageDetail[];
  key_lesson: string;
  real_world_action: string;
  encouragement: string;
}

export type DrillUserAction = "identified_scam" | "fell_for_it" | "no_response";

export interface DrillRespondOut {
  drill_id: string;
  script_id: string;
  scam_type: string;
  user_action: DrillUserAction;
  reaction_time_seconds: number;
  stages_caught: string[];
  stages_missed: string[];
  trigger_stage: string | null;
  drill_score: number;
  score_before: number;
  score_after: number;
  change: number;
  label: string;
  debrief: DrillDebrief;
}

export interface ScoreHistoryEntry {
  drill_number: number;
  score: number;
  scam_type: string;
  date: string;
}

export interface DrillScoreOut {
  user_id: string;
  current_score: number;
  previous_score: number;
  change: number;
  label: string;
  drills_completed: number;
  best_reaction_time: number | null;
  weakest_scam_type: string | null;
  history: ScoreHistoryEntry[];
}

export interface ScamTypeInfo {
  id: string;
  label: string;
  default_difficulty: string;
  /** Estimated call length in seconds (from the fallback template). */
  estimated_duration_seconds?: number;
}

export interface DrillUploadOut {
  voice_clip_url: string;
  duration_seconds: number;
  status: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export const drillApi = {
  createProfile: (body: DrillProfileRequest) =>
    api.post<DrillProfileOut>("/drill/profile", body),

  uploadVoice: async (profileId: string, file: File): Promise<DrillUploadOut> => {
    const form = new FormData();
    form.append("profile_id", profileId);
    form.append("file", file);
    const res = await fetch(`${API_URL}/drill/upload-voice`, {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new ApiError(res.status, text || res.statusText);
    }
    return (await res.json()) as DrillUploadOut;
  },

  generateScript: (body: { profile_id: string; scam_type: string; difficulty: string }) =>
    api.post<DrillScriptOut>("/drill/generate-script", body),

  synthesizeVoice: (body: { script_id: string; method?: string }) =>
    api.post<DrillSynthesizeOut>("/drill/synthesize-voice", body),

  respond: (body: {
    script_id: string;
    user_action: DrillUserAction;
    reaction_time_seconds: number;
    audio_position_seconds: number;
  }) => api.post<DrillRespondOut>("/drill/respond", body),

  getScore: (userId: string) =>
    api.get<DrillScoreOut>(`/drill/score/${encodeURIComponent(userId)}`),

  getScamTypes: () => api.get<{ scam_types: ScamTypeInfo[] }>("/drill/scam-types"),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const USER_ID_KEY = "mirage_user_id";

/** Stable per-browser user id, persisted so resilience history survives reloads. */
export function getUserId(): string {
  if (typeof window === "undefined") return "anonymous";
  try {
    let id = window.localStorage.getItem(USER_ID_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `uid-${Math.random().toString(36).slice(2)}-${Date.now()}`;
      window.localStorage.setItem(USER_ID_KEY, id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

/** Resolve a backend-relative media path (/media/drill/x.mp3) to an absolute URL. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

/** Bank short keys accepted by the backend (maps to full names server-side). */
export const BANK_OPTIONS = [
  { id: "sbi", label: "State Bank of India" },
  { id: "hdfc", label: "HDFC Bank" },
  { id: "icici", label: "ICICI Bank" },
  { id: "axis", label: "Axis Bank" },
  { id: "kotak", label: "Kotak Mahindra Bank" },
  { id: "pnb", label: "Punjab National Bank" },
  { id: "bob", label: "Bank of Baroda" },
  { id: "yes", label: "Yes Bank" },
  { id: "canara", label: "Canara Bank" },
  { id: "idbi", label: "IDBI Bank" },
] as const;

/** Fallback list matching GET /drill/scam-types (used if the probe fails). */
export const FALLBACK_SCAM_TYPES: ScamTypeInfo[] = [
  { id: "bank_kyc", label: "Bank KYC Fraud", default_difficulty: "medium", estimated_duration_seconds: 63 },
  { id: "fedex", label: "FedEx / Customs Parcel", default_difficulty: "medium", estimated_duration_seconds: 57 },
  { id: "relative_distress", label: "Relative in Distress", default_difficulty: "hard", estimated_duration_seconds: 58 },
  { id: "rbi_police", label: "RBI / Police Impersonation", default_difficulty: "hard", estimated_duration_seconds: 58 },
  { id: "job_offer", label: "Job Offer / Work-from-Home", default_difficulty: "easy", estimated_duration_seconds: 64 },
];

/**
 * Pre-generated demo audios (frontend/public/audio/drill/<id>.mp3) — generated
 * offline with edge-tts so the demo survives without live synthesis.
 */
export function pregeneratedAudioUrl(scamType: string): string {
  return `/audio/drill/${scamType}.mp3`;
}
