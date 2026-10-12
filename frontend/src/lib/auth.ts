/** Lightweight client identity — UUID persisted in localStorage.
 *
 * Demo mode (plan §7.3): when NEXT_PUBLIC_DEMO_USER_ID is set, the app uses
 * that stable id instead of a random one, so the dashboard shows the seeded
 * Priya Sharma profile, drill history (25 → 42 → 67), and family group.
 */

const DEMO_USER_ID = process.env.NEXT_PUBLIC_DEMO_USER_ID || "";
const USER_KEY = "mirage_user_id";
const FAMILY_KEY = "mirage_family_group_id";
const NAME_KEY = "mirage_display_name";

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `u_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export function getUserId(): string {
  if (DEMO_USER_ID) return DEMO_USER_ID;
  if (typeof window === "undefined") return "anonymous";
  let id = localStorage.getItem(USER_KEY);
  if (!id) {
    id = uuid();
    localStorage.setItem(USER_KEY, id);
  }
  return id;
}

export function getDisplayName(): string {
  if (DEMO_USER_ID) return localStorage.getItem(NAME_KEY) || "Priya";
  if (typeof window === "undefined") return "friend";
  return localStorage.getItem(NAME_KEY) || "friend";
}

export function setDisplayName(name: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(NAME_KEY, name.trim() || "friend");
}

export function getFamilyGroupId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(FAMILY_KEY);
}

export function setFamilyGroupId(id: string | null): void {
  if (typeof window === "undefined") return;
  if (!id) localStorage.removeItem(FAMILY_KEY);
  else localStorage.setItem(FAMILY_KEY, id);
}
