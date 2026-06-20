import { supabase } from "@/lib/supabase";
import { CommentCard, type CommentTarget } from "@/components/comment-card";

export const dynamic = "force-dynamic";

// The "posts to comment on" feed — its own top-level tab.
// Influencer/keyword posts that have a pre-drafted comment and haven't been
// engaged yet. Found safely via Firecrawl (no LinkedIn login).
export default async function CommentsPage() {
  // Influencer posts only — comment_finder feeds this daily (Groups sunset).
  const infRes = await supabase
    .from("influencer_posts")
    .select("id, body, post_url, relevance_score, suggested_action, suggested_comment, posted_at, influencers(full_name, handle, profile_url)")
    .eq("our_engagement_status", "none")
    .gte("relevance_score", 50)
    .order("relevance_score", { ascending: false })
    .limit(200);

  const targets: CommentTarget[] = [];
  for (const p of infRes.data ?? []) {
    const inf = (p as any).influencers;
    targets.push({
      id: p.id,
      kind: "influencer",
      source: inf?.full_name || (inf?.handle ? `@${inf.handle}` : "Someone"),
      sourceUrl: inf?.profile_url,
      body: p.body ?? "",
      postUrl: p.post_url,
      score: p.relevance_score,
      action: p.suggested_action,
      comment: p.suggested_comment,
    });
  }
  targets.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  return (
    <div className="space-y-3">
      <div className="card !p-4">
        <h2 className="text-lg font-semibold">💬 Comments — posts to engage with</h2>
        <p className="text-sm text-gray-600 mt-1">
          {targets.length} posts queued, each with a comment drafted in your
          voice. Open the post, paste/adapt the comment, then mark it done.
          Found safely via search — no LinkedIn automation on your account.
        </p>
        <div className="flex gap-4 mt-2 text-xs text-gray-500">
          <span><b className="text-gray-800">{targets.length}</b> posts from people you track + AI keywords</span>
        </div>
      </div>

      {targets.length === 0 ? (
        <div className="card text-center text-gray-500 py-8 text-sm">
          No posts queued right now. New comment targets are found from your
          tracked influencers + AI keywords. Check back after the next run.
        </div>
      ) : (
        <div className="space-y-2">
          {targets.map((t) => (
            <CommentCard key={`${t.kind}:${t.id}`} t={t} />
          ))}
        </div>
      )}
    </div>
  );
}
