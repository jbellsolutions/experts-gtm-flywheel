"use client";
import { useState, useTransition } from "react";
import { enqueuePostLeadgen, saveOfferFramework } from "@/app/actions";
import { OFFERS, DEFAULT_OFFER } from "@/lib/leadgen-offers";

// Paste a LinkedIn post URL → the worker scrapes the author + post + every
// commenter and dedupes them into leads. Enrichment + offer-email drafting happen
// per-lead, on demand, from the Leads table below (so credits aren't spent on
// commenters the team won't work). The offer frameworks here drive those emails.
export function PostLeadgenBox({ frameworks }: { frameworks: Record<string, string> }) {
  const [url, setUrl] = useState("");
  const [offer, setOffer] = useState(DEFAULT_OFFER);
  const [fw, setFw] = useState(frameworks[DEFAULT_OFFER] || "");
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState("");
  const [saved, setSaved] = useState("");

  function pickOffer(slug: string) {
    setOffer(slug);
    setFw(frameworks[slug] || "");
    setSaved("");
  }
  function run() {
    if (!url.trim()) return;
    start(async () => {
      const r = await enqueuePostLeadgen(url.trim());
      setMsg(r?.error ? `⚠ ${r.error}` : "Queued ✓ — commenters get scraped + deduped within ~2 min. Refresh, then Enrich the leads you want.");
      if (!r?.error) setUrl("");
    });
  }
  function save() {
    start(async () => {
      await saveOfferFramework(offer, fw);
      setSaved("Saved ✓");
      setTimeout(() => setSaved(""), 1500);
    });
  }

  const current = OFFERS.find((o) => o.slug === offer);

  return (
    <div className="card !p-4 space-y-4">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-800">Scrape a post → build leads</h3>
        <p className="text-[11px] text-gray-500">
          Paste a LinkedIn post URL. We pull the author + the post + <b>every commenter</b> and
          dedupe them into leads below. Then <b>Enrich</b> the ones worth working — that fills
          company + verified email and drafts the offer email for that lead only.
        </p>
        <div className="flex gap-2">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.linkedin.com/posts/…  or  /feed/update/…"
            className="flex-1 text-sm rounded border border-gray-300 p-2 focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button onClick={run} disabled={pending || !url.trim()}
            className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:opacity-90 disabled:opacity-40">
            {pending ? "…" : "Scrape & build"}
          </button>
        </div>
        {msg && <p className="text-[11px] text-gray-600">{msg}</p>}
      </div>

      <div className="border-t border-gray-100 pt-3 space-y-1.5">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <label className="text-xs font-semibold text-gray-700">Offer framework (drives the emails)</label>
          <div className="flex items-center gap-2">
            <select value={offer} onChange={(e) => pickOffer(e.target.value)}
              className="text-xs rounded border border-gray-300 p-1 focus:outline-none focus:ring-2 focus:ring-accent">
              {OFFERS.map((o) => (
                <option key={o.slug} value={o.slug}>{o.label}{o.live ? "" : " (not live yet)"}</option>
              ))}
            </select>
            <button onClick={save} disabled={pending}
              className="px-2.5 py-1 text-xs rounded border border-gray-300 text-gray-700 hover:bg-gray-50">
              Save {saved}
            </button>
          </div>
        </div>
        {current && !current.live && (
          <p className="text-[10px] text-amber-600">
            {current.label} isn't wired up yet — you can paste copy here to save it, but emails
            won't use it until it's turned on.
          </p>
        )}
        <textarea
          value={fw}
          onChange={(e) => setFw(e.target.value)}
          rows={6}
          placeholder="Paste the offer + email structure here: WHO it's for, the core promise, the proof, the soft CTA. The generator follows this for every email on this offer."
          className="w-full text-sm rounded border border-gray-300 p-2 font-mono focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <p className="text-[10px] text-gray-400">Editable anytime — no redeploy. Each lead's email = this offer × what they said × their profile, in the chosen brand voice.</p>
      </div>
    </div>
  );
}
