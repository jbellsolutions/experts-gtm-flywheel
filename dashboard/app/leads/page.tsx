import { supabase } from "@/lib/supabase";
import { PostLeadgenBox } from "@/components/post-leadgen-box";

export const dynamic = "force-dynamic";

// Leads now live in the Airtable CRM. This tab just kicks off scrapes (paste a
// post, or use the plugin), shows job status, and links to Airtable where the
// team works the contacts (pick voice + offer; check Enrich / Create email / Rerun).
export default async function LeadsPage() {
  const [{ data: jobs }, { data: settings }] = await Promise.all([
    supabase
      .from("leadgen_jobs")
      .select("id, status, stats, caps, created_at, error")
      .order("created_at", { ascending: false })
      .limit(12),
    supabase.from("app_settings").select("key,value").like("key", "offer_framework%"),
  ]);

  const fwRows = (settings ?? []) as { key: string; value: string }[];
  const legacyFw = fwRows.find((r) => r.key === "offer_framework")?.value || "";
  const frameworks: Record<string, string> = {
    your_offer: fwRows.find((r) => r.key === "offer_framework:your_offer")?.value || legacyFw,
  };

  const baseId = process.env.AIRTABLE_BASE_ID || "";
  const airtableUrl = baseId ? `https://airtable.com/${baseId}` : "";

  return (
    <div className="space-y-3">
      <div className="card !p-4">
        <h2 className="text-lg font-semibold">🧲 Leads</h2>
        <p className="text-sm text-gray-600 mt-0.5">
          Paste a post (or use the plugin) → the worker scrapes + dedupes its commenters into the{" "}
          <b>Airtable CRM</b>. Work them there: pick a voice + offer, then check <b>Enrich</b> /{" "}
          <b>Create email</b> / <b>Rerun</b> per contact.
        </p>
        {airtableUrl ? (
          <a href={airtableUrl} target="_blank" rel="noreferrer"
            className="inline-block mt-2 px-3 py-1.5 text-sm rounded bg-accent text-white hover:opacity-90">
            Open the Leads CRM in Airtable →
          </a>
        ) : (
          <p className="text-[11px] text-amber-600 mt-2">Airtable base not configured yet (set AIRTABLE_BASE_ID).</p>
        )}
      </div>

      <PostLeadgenBox frameworks={frameworks} />

      <div className="card !p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">Recent scrape jobs</h3>
        {(jobs ?? []).length === 0 ? (
          <p className="text-xs text-gray-400">No jobs yet — paste a post above to start one.</p>
        ) : (
          <div className="space-y-1.5">
            {(jobs ?? []).map((j: any) => {
              const caps = j.caps || {};
              const label = caps.post_url || (caps.mode === "post" ? "post scrape" : "influencer crawl");
              const leads = j.stats?.new_leads;
              const color =
                j.status === "done" ? "bg-green-100 text-green-700"
                : j.status === "running" ? "bg-blue-100 text-blue-700"
                : j.status === "failed" ? "bg-red-100 text-red-700"
                : "bg-gray-100 text-gray-600";
              return (
                <div key={j.id} className="flex items-center justify-between gap-2 text-xs border border-gray-100 rounded p-2">
                  <span className="truncate text-gray-700" title={label}>{label}</span>
                  <span className="flex items-center gap-2 shrink-0">
                    {leads != null && <span className="text-gray-500">{leads} → Airtable</span>}
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${color}`}>{j.status}</span>
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
