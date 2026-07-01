import { supabase } from "@/lib/supabase";

// Thin server-side client for the SpeakerAgent API.
// The live feature is PODCASTS (conferences/leads were retired → 410). Podcasts are
// Airtable records exposed as { id, ...DisplayCasedFields }. Auth = a single X-API-Key
// header + a speaker_id query param. Config: env first, then the app_settings "Connect
// SpeakerAgent" form. Read live; no local mirror.

export type SpeakerPodcast = { id: string; [field: string]: any };

type Cfg = { url?: string; key?: string; speakerId?: string };

async function cfg(): Promise<Cfg> {
  const env: Cfg = {
    url: process.env.SPEAKERAGENT_API_URL,
    key: process.env.SPEAKERAGENT_API_KEY,
    speakerId: process.env.SPEAKERAGENT_SPEAKER_ID,
  };
  if (env.url && env.key && env.speakerId) return env;
  let m: Record<string, string> = {};
  try {
    const { data } = await supabase
      .from("app_settings")
      .select("key,value")
      .like("key", "speakeragent:%");
    m = Object.fromEntries((data ?? []).map((r: any) => [r.key, r.value]));
  } catch {
    /* app_settings unavailable at build time */
  }
  return {
    url: env.url || m["speakeragent:api_url"],
    key: env.key || m["speakeragent:api_key"],
    speakerId: env.speakerId || m["speakeragent:speaker_id"],
  };
}

export async function isConfigured(): Promise<boolean> {
  const c = await cfg();
  return Boolean(c.url && c.key && c.speakerId);
}

function endpoint(base: string, path: string): string {
  return base.replace(/\/+$/, "") + path;
}

async function call(method: string, path: string, body?: any): Promise<Response | null> {
  const c = await cfg();
  if (!c.url || !c.key) return null;
  try {
    return await fetch(endpoint(c.url, path), {
      method,
      headers: { "X-API-Key": c.key, "Content-Type": "application/json" },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      cache: "no-store",
    });
  } catch {
    return null;
  }
}

// The speaker's active podcast leads. No status filter — fresh podcasts have an empty
// Lead Status, so we show all active and let the card surface status/triage.
export async function listPodcasts(): Promise<SpeakerPodcast[]> {
  const c = await cfg();
  if (!c.url || !c.key || !c.speakerId) return [];
  const u = new URL(endpoint(c.url, "/api/podcasts"));
  u.searchParams.set("speaker_id", c.speakerId);
  const r = await call("GET", `/api/podcasts?${u.searchParams.toString()}`);
  if (!r || !r.ok) return [];
  const j = await r.json();
  return (j.podcasts ?? []) as SpeakerPodcast[];
}

// Two-way sync: move the podcast's status inside SpeakerAgent (no auto-send email on any
// status — unlike the old leads endpoint — so all values are safe).
export async function setPodcastStatus(id: string, status: string): Promise<void> {
  await call("PUT", `/api/podcasts/${id}/status`, { status, updated_by: "flywheel-dashboard" });
}

// Toggle the Saved ♥ flag.
export async function setPodcastSaved(id: string, saved: boolean): Promise<void> {
  await call("PUT", `/api/podcasts/${id}/saved`, { saved });
}

// Enrich the host contact + generate the outreach pitch (Email Subject/Draft) — raw
// podcasts have no draft until this runs.
export async function refreshPodcast(id: string): Promise<void> {
  await call("POST", `/api/podcasts/${id}/refresh`);
}
