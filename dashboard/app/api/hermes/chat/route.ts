import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// Cold Email "Hermes" chat proxy. Forwards the conversation to prospect-api /hermes/chat
// server-side (with the X-API-Key, so the browser never holds it). When Hermes signals the
// campaign spec is ready, we enqueue a leadgen_jobs row (mode: hermes_campaign) — the worker
// creates the UNSTARTED SmartLead campaign + ingests the leads to Airtable for review.
// Nothing is sent here; nothing sends until the operator STARTs the campaign in SmartLead.
export async function POST(req: NextRequest) {
  const base = process.env.PROSPECT_API_URL;
  const key = process.env.PROSPECT_API_KEY;
  if (!base || !key) {
    return NextResponse.json(
      { error: "Cold-email API not configured (set PROSPECT_API_URL + PROSPECT_API_KEY)." },
      { status: 500 }
    );
  }
  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  const messages = payload?.messages ?? [];
  const context = payload?.context ?? {};

  let data: any;
  try {
    const r = await fetch(`${base.replace(/\/$/, "")}/hermes/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: JSON.stringify({ messages, context }),
      cache: "no-store",
    });
    data = await r.json();
    if (!r.ok) {
      return NextResponse.json(
        { error: data?.detail || `prospect-api ${r.status}` },
        { status: r.status }
      );
    }
  } catch (e: any) {
    return NextResponse.json({ error: String(e?.message || e) }, { status: 502 });
  }

  // Still gathering the spec → just return the reply.
  if (!data?.ready || !data?.campaign) {
    return NextResponse.json({ reply: data?.reply || "", enqueued: false });
  }

  // Ready → build the job caps and enqueue (the worker owns SmartLead + Airtable).
  const c = data.campaign;
  const source =
    c.source_type === "list"
      ? { leads: Array.isArray(context.uploaded_leads) ? context.uploaded_leads : [] }
      : { post_url: c.post_url || "" };
  const caps = {
    mode: "hermes_campaign",
    campaign_name: c.campaign_name || "Cold Email Campaign",
    offer_label: c.offer_label || "",
    voice_label: c.voice_label || "",
    framework: c.framework || "",
    source,
  };
  const { data: job, error } = await supabase
    .from("leadgen_jobs")
    .insert({ status: "queued", caps, influencer_ids: [] })
    .select("id")
    .single();
  if (error) {
    return NextResponse.json({
      reply: data.reply,
      enqueued: false,
      error: `enqueue failed: ${error.message}`,
    });
  }
  return NextResponse.json({ reply: data.reply, enqueued: true, job_id: job?.id, campaign: caps });
}
