/** API base URL. Overridable via NEXT_PUBLIC_API_URL (frontend/.env.local). */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/drill", label: "Fire Drills" },
  { href: "/guardian", label: "Guardian" },
  { href: "/graph", label: "Scam Map" },
] as const;

export const SCAM_TYPES = [
  { id: "bank_kyc", label: "Bank KYC / Update" },
  { id: "fedex", label: "Fake Parcel / FedEx" },
  { id: "otp", label: "OTP Phishing" },
  { id: "lottery", label: "Lottery / Prize" },
  { id: "job_offer", label: "Fake Job Offer" },
  { id: "relative_distress", label: "Relative in Distress" },
  { id: "investment", label: "Investment Scam" },
  { id: "romance", label: "Romance Scam" },
] as const;

export const LANGUAGES = [
  { id: "en", label: "English" },
  { id: "hi", label: "हिन्दी" },
  { id: "ta", label: "தமிழ்" },
] as const;

/** Placeholder resilience-score history until Phase 3 ships real data. */
export const SCORE_HISTORY = [
  { day: "Mon", score: 42 },
  { day: "Tue", score: 48 },
  { day: "Wed", score: 51 },
  { day: "Thu", score: 57 },
  { day: "Fri", score: 63 },
  { day: "Sat", score: 61 },
  { day: "Sun", score: 68 },
];

/** Placeholder IOC counts for the Phase 5 graph teaser. */
export const GRAPH_STATS = [
  { label: "Phones", value: 1240 },
  { label: "UPI IDs", value: 812 },
  { label: "Domains", value: 96 },
  { label: "Campaigns", value: 31 },
];
