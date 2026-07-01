"use server";
import { revalidatePath } from "next/cache";
import { supabase } from "@/lib/supabase";
import { setPodcastStatus, setPodcastSaved, refreshPodcast } from "@/lib/speakeragent";

// Draft status changes show up on /drafts, /newsletter (filtered view), and
// /today (counts). Revalidate all three so an approve on the Newsletter tab
// actually reflects there instead of appearing to "go back to pending."
function revalidateDraftViews() {
  revalidatePath("/drafts");
  revalidatePath("/newsletter");
  revalidatePath("/today");
}

// ── SpeakerAgent integration ──────────────────────────────────────────────
export async function saveSpeakerAgentConfig(formData: FormData) {
  const rows = [
    { key: "speakeragent:api_url", value: String(formData.get("api_url") || "").trim() },
    { key: "speakeragent:api_key", value: String(formData.get("api_key") || "").trim() },
    { key: "speakeragent:speaker_id", value: String(formData.get("speaker_id") || "").trim() },
  ].filter((r) => r.value);
  if (rows.length) await supabase.from("app_settings").upsert(rows, { onConflict: "key" });
  revalidatePath("/speakeragent");
}

export async function actionSpeakerLead(id: string, status: string) {
  await setPodcastStatus(id, status);
  revalidatePath("/speakeragent");
}

export async function actionSpeakerSaved(id: string, saved: boolean) {
  await setPodcastSaved(id, saved);
  revalidatePath("/speakeragent");
}

export async function actionSpeakerRefresh(id: string) {
  await refreshPodcast(id);
  revalidatePath("/speakeragent");
}

// ── Drafts ─────────────────────────────────────────────────────────────
export async function approveDraft(id: string, body?: string) {
  const update: any = { status: "approved" };
  if (body !== undefined) {
    update.body = body;
    update.status = "edited";
    update.edit_diff = "user-edited";
  }
  await supabase.from("drafts").update(update).eq("id", id);
  revalidateDraftViews();
}
export async function rejectDraft(id: string) {
  await supabase.from("drafts").update({ status: "rejected" }).eq("id", id);
  revalidateDraftViews();
}
export async function approveAll(ids: string[]) {
  if (!ids.length) return;
  await supabase.from("drafts").update({ status: "approved" }).in("id", ids);
  revalidateDraftViews();
}
export async function retryDraft(id: string) {
  // Failed drafts go back to 'approved' so the next publish cron picks them up.
  // Clear the error from metadata; keep the rest.
  const { data } = await supabase.from("drafts").select("metadata").eq("id", id).single();
  const md = (data?.metadata ?? {}) as Record<string, any>;
  delete md.error;
  md.last_retry_at = new Date().toISOString();
  await supabase.from("drafts").update({ status: "approved", metadata: md }).eq("id", id);
  revalidateDraftViews();
}

export async function deleteDraft(id: string) {
  // Hard-delete a draft (pending/unpublished). Used by the dashboard Delete button.
  await supabase.from("drafts").delete().eq("id", id);
  revalidateDraftViews();
}

export async function rerunDraft(id: string) {
  // Flag the draft for regeneration: the worker's rerun_drain cron (every 2 min)
  // picks up any draft with metadata.rerun_requested_at and rewrites it in its
  // voice with a fresh trend/industry/CTA. Clear the stale visual so it
  // re-renders, and reset to pending.
  const { data } = await supabase.from("drafts").select("metadata").eq("id", id).single();
  const md = { ...((data?.metadata as Record<string, any>) ?? {}) };
  md.rerun_requested_at = new Date().toISOString();
  delete md.visual;
  delete md.visual_error;
  await supabase.from("drafts").update({ status: "pending", metadata: md }).eq("id", id);
  revalidateDraftViews();
}

export async function snoozeDraft(id: string, days: number = 1) {
  const { data } = await supabase.from("drafts").select("scheduled_for").eq("id", id).single();
  if (!data) return;
  const next = new Date(data.scheduled_for);
  next.setDate(next.getDate() + days);
  await supabase.from("drafts").update({ scheduled_for: next.toISOString() }).eq("id", id);
  revalidateDraftViews();
}

// ── Prospecting (VA outreach generator) ─────────────────────────────────
// Calls the prospect-api service server-side so the shared secret never
// reaches the browser. Returns generated draft variants (or {error}).
export async function generateProspect(input: {
  channel: string;
  voice?: string;
  prospectUrl?: string;
  prospectText?: string;
  postUrl?: string;
  postText?: string;
  threadText?: string;
}) {
  const base = process.env.PROSPECT_API_URL;
  const key = process.env.PROSPECT_API_KEY;
  if (!base || !key) return { error: "Prospecting API not configured (set PROSPECT_API_URL + PROSPECT_API_KEY)." };
  try {
    const r = await fetch(`${base.replace(/\/$/, "")}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: JSON.stringify({
        channel: input.channel,
        prospect_url: input.prospectUrl || null,
        prospect_text: input.prospectText || null,
        post_url: input.postUrl || null,
        post_text: input.postText || null,
        thread_text: input.threadText || null,
        voice: input.voice || "ai_guy",
      }),
      cache: "no-store",
    });
    const text = await r.text();
    if (!r.ok) return { error: `API ${r.status}: ${text.slice(0, 200)}` };
    return JSON.parse(text);
  } catch (e: any) {
    return { error: String(e?.message || e) };
  }
}

// ── Lead-gen (influencer commenters -> ICP -> enrich) ────────────────────
// Up-front credit estimate, mirrors leadgen/pipeline.py::estimate_credits so the
// number the user sees matches what the worker will spend.
function estimateLeadgenCredits(n: number, c: Record<string, any>): number {
  const perInf = 1 + (c.posts_examined ?? 12);
  const commenters = (c.top_posts ?? 5) * Math.min(c.max_commenters ?? 40, 30);
  const headline = Math.round(commenters * 0.4);
  return n * perInf + n * headline;
}

export async function enqueueLeadgen(
  influencerIds: string[],
  caps?: Record<string, any>
) {
  if (!influencerIds.length) return { error: "Pick at least one influencer to crawl." };
  const c = {
    top_posts: 5, posts_examined: 12, min_comments: 10, max_commenters: 40,
    since_days: 90, max_enrich: 200, enrich: true, ...(caps ?? {}),
  };
  const estimate = estimateLeadgenCredits(influencerIds.length, c);
  const { error } = await supabase.from("leadgen_jobs").insert({
    influencer_ids: influencerIds,
    caps: c,
    estimate: { credits: estimate },
    status: "queued",
  });
  revalidatePath("/leads");
  if (error) return { error: error.message };
  return { ok: true, estimate };
}

// Per-row manual enrich — the whole point of the on-demand flow. Captures the
// chosen voice + offer onto the lead (in `raw`, no schema change), then flags it
// 'queued'. The worker's drain_enrich_queue (every 3 min) then runs Bright Data
// (company) + FullEnrich (verified email) + drafts the offer email in that voice +
// offer. Credits are only spent on leads the team actually picks.
export async function enqueueEnrich(leadId: string, voice?: string, offer?: string) {
  const { data } = await supabase.from("lead_contacts").select("raw").eq("id", leadId).maybeSingle();
  const raw: Record<string, any> = { ...((data?.raw as Record<string, any>) ?? {}) };
  if (voice) raw.draft_voice = voice;
  if (offer) raw.draft_offer = offer;
  await supabase.from("lead_contacts").update({ enrichment_status: "queued", raw }).eq("id", leadId);
  revalidatePath("/leads");
}

// Paste-a-post → leads. Enqueues a post-mode job; the worker scrapes the post's
// author + post + ALL commenters, dedupes, enriches everyone, and auto-drafts a
// custom offer email per enriched lead. Also called by the extension via /api/leadgen.
export async function enqueuePostLeadgen(postUrl: string) {
  const url = (postUrl || "").trim();
  if (!url.startsWith("http")) return { error: "Paste a full LinkedIn post URL." };
  const { error } = await supabase.from("leadgen_jobs").insert({
    influencer_ids: [],
    caps: { mode: "post", post_url: url },
    status: "queued",
  });
  revalidatePath("/leads");
  return error ? { error: error.message } : { ok: true };
}

// Per-offer framework copy the email generator follows (editable, no redeploy).
// Keyed offer_framework:<slug> — one per offer. Editing your primary offer also
// writes the legacy 'offer_framework' key so the worker's fallback stays in sync.
// ── Cold Email (Hermes) config ────────────────────────────────────────────
export async function saveHermesConfig(formData: FormData) {
  const rows = [
    { key: "hermes:business_info", value: String(formData.get("business_info") || "").trim() },
    { key: "smartlead:api_key", value: String(formData.get("smartlead_api_key") || "").trim() },
  ].filter((r) => r.value);
  if (rows.length) await supabase.from("app_settings").upsert(rows, { onConflict: "key" });
  revalidatePath("/hermes");
}

export async function saveOfferFramework(slug: string, text: string) {
  const rows = [{ key: `offer_framework:${slug}`, value: text, updated_at: new Date().toISOString() }];
  if (slug === "your_offer") {
    rows.push({ key: "offer_framework", value: text, updated_at: new Date().toISOString() });
  }
  await supabase.from("app_settings").upsert(rows, { onConflict: "key" });
  revalidatePath("/leads");
  return { ok: true };
}

// ── Inbox ──────────────────────────────────────────────────────────────
// ── Daily checklist ────────────────────────────────────────────────────
export async function toggleChecklistItem(date: string, itemId: string, completed: boolean) {
  const { data } = await supabase
    .from("daily_checklists")
    .select("items")
    .eq("date", date)
    .single();
  if (!data) return;
  const items = (data.items as any[]).map((it) =>
    it.id === itemId
      ? { ...it, completed, completed_at: completed ? new Date().toISOString() : null }
      : it
  );
  await supabase
    .from("daily_checklists")
    .update({ items, updated_at: new Date().toISOString() })
    .eq("date", date);
  revalidatePath("/today");
}

// ── Ideas ──────────────────────────────────────────────────────────────
export async function boostIdea(id: string, delta: number = 10) {
  const { data } = await supabase.from("content_ideas").select("priority").eq("id", id).single();
  if (!data) return;
  const next = Math.max(0, Math.min(100, (data.priority ?? 50) + delta));
  await supabase.from("content_ideas").update({ priority: next }).eq("id", id);
  revalidatePath("/ideas");
}
export async function dismissIdea(id: string) {
  await supabase.from("content_ideas").update({ status: "dismissed" }).eq("id", id);
  revalidatePath("/ideas");
}
export async function useIdeaNow(id: string) {
  // Flag the idea for immediate repurposing. The use_now_drain cron fires
  // every 2 min on the worker and picks up any idea with
  // metadata.use_now_requested_at set, then generates one LinkedIn post +
  // one Substack post + one Medium article from it.
  const { data } = await supabase
    .from("content_ideas")
    .select("metadata")
    .eq("id", id)
    .single();
  const md = { ...((data?.metadata as Record<string, unknown>) ?? {}) };
  md.use_now_requested_at = new Date().toISOString();
  await supabase
    .from("content_ideas")
    .update({ priority: 100, metadata: md })
    .eq("id", id);
  revalidatePath("/ideas");
  revalidatePath("/drafts");
}
export async function addManualIdea(content: string) {
  if (!content.trim()) return;
  await supabase.from("content_ideas").insert({
    source: "manual",
    content: content.trim(),
    priority: 80,
  });
  revalidatePath("/ideas");
}

// ── Comment engagement (Comments tab) ──
export async function markPostEngaged(postId: string, action: string) {
  await supabase.from("influencer_posts").update({
    our_engagement_status: action,
  }).eq("id", postId);
  // Bump influencer.last_engaged_at
  const { data: post } = await supabase.from("influencer_posts").select("influencer_id").eq("id", postId).single();
  if (post?.influencer_id) {
    await supabase.from("influencers").update({
      last_engaged_at: new Date().toISOString(),
    }).eq("id", post.influencer_id);
  }
  revalidatePath("/comments");
}

