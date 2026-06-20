import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// Extension entry point: "Scrape this post → leads". Basic-auth is enforced by
// middleware (same dashboard password). Body: { post_url }. Enqueues a post-mode
// leadgen job; the worker does the scrape + enrich + email-draft.
export async function POST(req: NextRequest) {
  let url = "";
  try {
    url = ((await req.json())?.post_url || "").trim();
  } catch {
    return NextResponse.json({ error: "bad JSON" }, { status: 400 });
  }
  if (!url.startsWith("http")) {
    return NextResponse.json({ error: "post_url must be a full URL" }, { status: 400 });
  }
  const { error } = await supabase.from("leadgen_jobs").insert({
    influencer_ids: [],
    caps: { mode: "post", post_url: url },
    status: "queued",
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, queued: url });
}
