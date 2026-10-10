import { API_URL } from "./constants";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  providers: {
    configured?: string | null;
    available?: string[];
    supabase?: boolean;
    neo4j?: boolean;
    environment?: string;
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Phase 5 — Scammer Hunter + Scam Graph
// ---------------------------------------------------------------------------
export interface GraphNode {
  id: string;
  label: string;
  type: "PhoneNumber" | "UPI_ID" | "Domain" | "BankAccount" | "ScammerName";
  group: number;
  report_count: number;
  in_ring: boolean;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
}

export interface GraphStats {
  phone_numbers: number;
  upi_ids: number;
  domains: number;
  bank_accounts: number;
  scam_reports: number;
  rings: number;
  scam_type_counts: Record<string, number>;
  backend: "sqlite" | "neo4j";
}

export interface ScamRing {
  ring_id: string;
  size: number;
  node_ids: string[];
  phones: string[];
  upi_ids: string[];
  domains: string[];
  bank_accounts: string[];
}

export interface GraphRings {
  rings: ScamRing[];
  shared: {
    shared_upis: { upi_id: string; phones: string[]; phone_count: number }[];
    shared_domains: { domain: string; phones: string[]; phone_count: number }[];
  };
}

export interface MapCity {
  city: string;
  lat: number;
  lng: number;
  scam_count: number;
  top_type: string;
  intensity: number;
  trend: string;
}

export interface MapHeatmap {
  cities: MapCity[];
  national_stats: Record<string, unknown>;
}

export interface HoneypotTurn {
  session_id: string;
  reply: string;
  tactic_used: string;
  iocs_extracted_this_turn: Record<string, string[]>;
  total_iocs_extracted: number;
  conversation_health: "engaged" | "frustrated" | "about_to_hang_up";
  messages_in_session: number;
  estimated_time_wasted_seconds: number;
  mode: string;
}

export interface HoneypotScripted {
  messages: { role: string; text: string; tactic?: string }[];
  ioc_highlights: Record<string, string>;
  persona_name: string;
}

export interface ReportResult {
  report_id: string;
  report_text: string;
  helpline_script: string;
  urgent: boolean;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  health: () => request<HealthResponse>("/health"),

  // Phase 5
  graphData: (limit = 200) => request<GraphData>(`/graph/data?limit=${limit}`),
  graphStats: () => request<GraphStats>("/graph/stats"),
  graphRings: () => request<GraphRings>("/graph/rings"),
  mapHeatmap: () => request<MapHeatmap>("/map/heatmap"),
  honeypotStart: (scammer_message: string, persona = "ramesh", mode = "live") =>
    request<HoneypotTurn>("/honeypot/start", {
      method: "POST",
      body: JSON.stringify({ scammer_message, persona, mode }),
    }),
  honeypotContinue: (session_id: string, scammer_message: string, mode?: string) =>
    request<HoneypotTurn>("/honeypot/continue", {
      method: "POST",
      body: JSON.stringify({ session_id, scammer_message, mode }),
    }),
  honeypotScripted: () => request<HoneypotScripted>("/honeypot/scripted"),
  reportGenerate: (body: Record<string, unknown>) =>
    request<ReportResult>("/report/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
