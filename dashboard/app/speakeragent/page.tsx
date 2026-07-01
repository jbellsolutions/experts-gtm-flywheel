import { listPodcasts, isConfigured } from "@/lib/speakeragent";
import { SpeakerLeadCard } from "@/components/speaker-lead-card";
import { saveSpeakerAgentConfig } from "@/app/actions";

export const dynamic = "force-dynamic";

// Pulls the connected speaker's leads from SpeakerAgent.ai and shows them as square
// cards. Click a card → review the pre-written pitch, open LinkedIn / the event site,
// send from your own Gmail. Status changes sync back to SpeakerAgent. No local mirror.
export default async function SpeakerAgentPage() {
  if (!(await isConfigured())) {
    return (
      <div className="card !p-4 max-w-md">
        <h2 className="text-lg font-semibold">🎤 Connect SpeakerAgent</h2>
        <p className="text-sm text-gray-600 mt-1 mb-3">
          Paste your SpeakerAgent API details to pull in your podcast leads. (Stored on your
          own dashboard; only used server-side to call the API.)
        </p>
        <form action={saveSpeakerAgentConfig} className="space-y-2">
          <input name="api_url" placeholder="API URL — e.g. https://api.speakeragent.ai"
            className="w-full border border-gray-200 rounded px-2 py-1 text-sm" />
          <input name="api_key" placeholder="X-API-Key"
            className="w-full border border-gray-200 rounded px-2 py-1 text-sm" />
          <input name="speaker_id" placeholder="speaker_id"
            className="w-full border border-gray-200 rounded px-2 py-1 text-sm" />
          <button type="submit" className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:opacity-90">
            Connect
          </button>
        </form>
      </div>
    );
  }

  const pods = await listPodcasts();
  return (
    <div className="space-y-3">
      <div className="card !p-4">
        <h2 className="text-lg font-semibold">🎤 SpeakerAgent — podcasts to pitch</h2>
        <p className="text-sm text-gray-600 mt-0.5">
          <b>{pods.length}</b> podcast leads. Click a card → review the match + hook, hit{" "}
          <b>Generate pitch</b> to enrich the host + draft the email, then send from your Gmail.
          Status + Saved sync back to SpeakerAgent.
        </p>
      </div>
      {pods.length === 0 ? (
        <div className="card text-center text-gray-400 py-8 text-sm">
          No podcasts right now — check back after your next SpeakerAgent scout run.
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {pods.map((p) => (
            <SpeakerLeadCard key={p.id} lead={p} />
          ))}
        </div>
      )}
    </div>
  );
}
