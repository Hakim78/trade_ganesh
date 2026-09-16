import type { Dashboard, LiveState } from "./types";

const DASHBOARD_URL = "/data/dashboard.json";
const LIVE_URL = "/data/live/state.json";

async function getJson<T>(url: string): Promise<T | null> {
  const response = await fetch(`${url}?_=${Date.now()}`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${url} : HTTP ${response.status}`);
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("json")) return null; // fallback SPA (index.html) = fichier absent
  return (await response.json()) as T;
}

export const fetchDashboard = () => getJson<Dashboard>(DASHBOARD_URL);
export const fetchLiveState = () => getJson<LiveState>(LIVE_URL);
