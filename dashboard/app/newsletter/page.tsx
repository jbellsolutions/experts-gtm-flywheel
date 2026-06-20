import { supabase } from "@/lib/supabase";
import { DraftCard } from "@/components/draft-card";
import { PublishedCard } from "@/components/published-card";
import { ApproveAllBar } from "@/components/approve-all-bar";

export const dynamic = "force-dynamic";

export default async function NewsletterPage({
  searchParams,
}: {
  searchParams?: { col?: string };
}) {
  const col = (searchParams?.col ?? "pending") as
    | "pending"
    | "approved"
    | "published";

  const now = new Date();
  const thirtyAgo = new Date(now);
  thirtyAgo.setDate(thirtyAgo.getDate() - 30);

  const [pendingRes, approvedRes, publishedRes] = await Promise.all([
    supabase
      .from("drafts")
      .select("*")
      .eq("platform", "newsletter")
      .eq("status", "pending")
      .order("scheduled_for", { ascending: true, nullsFirst: false }),
    supabase
      .from("drafts")
      .select("*")
      .eq("platform", "newsletter")
      .in("status", ["approved", "edited"])
      .order("scheduled_for"),
    supabase
      .from("drafts")
      .select("*")
      .eq("platform", "newsletter")
      .eq("status", "published")
      .gte("published_at", thirtyAgo.toISOString())
      .order("published_at", { ascending: false }),
  ]);

  const pending = pendingRes.data ?? [];
  const approved = approvedRes.data ?? [];
  const published = publishedRes.data ?? [];

  const list = col === "pending" ? pending : col === "approved" ? approved : published;

  return (
    <div className="space-y-3">
      <div className="card !p-4">
        <h2 className="text-lg font-semibold">📬 Newsletter (Kit)</h2>
        <p className="text-sm text-gray-600 mt-1">
          Newsletter drafts generated daily from your ideas. Approve the ones
          you want — they broadcast via Kit at the scheduled slot.
        </p>
      </div>

      <div className="flex gap-1 border-b border-gray-200">
        <Tab href="/newsletter?col=pending" active={col === "pending"} label="Pending" count={pending.length} />
        <Tab href="/newsletter?col=approved" active={col === "approved"} label="Approved" count={approved.length} />
        <Tab href="/newsletter?col=published" active={col === "published"} label="Published" count={published.length} />
      </div>

      {list.length === 0 ? (
        <div className="card text-center text-gray-500 py-8 text-sm">
          {col === "pending"
            ? "No newsletter drafts pending. The repurposer generates one per idea — drop an idea in the Ideas tab and hit Use Now."
            : col === "approved"
            ? "Nothing approved & queued."
            : "Nothing published in the last 30 days."}
        </div>
      ) : col === "published" ? (
        <div className="space-y-2">
          {list.map((d) => <PublishedCard key={d.id} draft={d} />)}
        </div>
      ) : (
        <div className="space-y-2">
          {col === "pending" && (
            <ApproveAllBar ids={pending.map((d) => d.id)} count={pending.length} />
          )}
          {list.map((d) => <DraftCard key={d.id} draft={d} />)}
        </div>
      )}
    </div>
  );
}

function Tab({ href, active, label, count }: { href: string; active: boolean; label: string; count: number }) {
  return (
    <a
      href={href}
      className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
        active ? "border-accent text-accent" : "border-transparent text-gray-500 hover:text-gray-900"
      }`}
    >
      {label} <span className="text-xs text-gray-400">({count})</span>
    </a>
  );
}
