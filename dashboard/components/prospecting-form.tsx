"use client";
import { useState, useTransition } from "react";
import { generateProspect } from "@/app/actions";

type ChannelDef = { id: string; label: string; needsPost?: boolean; needsThread?: boolean };
const CHANNELS: ChannelDef[] = [
  { id: "comment", label: "LinkedIn comment", needsPost: true },
  { id: "cold_dm", label: "Cold DM / first message" },
  { id: "connection_note", label: "Connection note" },
  { id: "dm_reply", label: "DM reply (in thread)", needsThread: true },
  { id: "email", label: "Email" },
  { id: "sms", label: "SMS" },
];

type Variant = { subject?: string; text: string; chars?: number; flags?: string[] };

function CopyBtn({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="btn btn-ghost text-xs"
      onClick={async () => { await navigator.clipboard.writeText(value); setDone(true); setTimeout(() => setDone(false), 1200); }}
    >
      {done ? "Copied ✓" : "Copy"}
    </button>
  );
}

export function ProspectingForm() {
  const VOICES = [
    { id: "ai_guy", label: "AI Guy" },
    { id: "human_loop", label: "Human-in-Loop" },
    { id: "ai_reality", label: "AI Reality-Check" },
  ];
  const [voice, setVoice] = useState<string>("ai_guy");
  const [channel, setChannel] = useState<string>("comment");
  const [prospectUrl, setProspectUrl] = useState("");
  const [prospectText, setProspectText] = useState("");
  const [postUrl, setPostUrl] = useState("");
  const [postText, setPostText] = useState("");
  const [threadText, setThreadText] = useState("");
  const [pending, start] = useTransition();
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>("");

  const cfg = CHANNELS.find((c) => c.id === channel)!;
  const isEmail = channel === "email";

  function run() {
    setError(""); setResult(null);
    start(async () => {
      const r = await generateProspect({
        channel, voice, prospectUrl, prospectText, postUrl, postText, threadText,
      });
      if (r?.error) setError(r.error);
      else setResult(r);
    });
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <div className="flex flex-wrap gap-2">
          {CHANNELS.map((c) => (
            <button
              key={c.id}
              onClick={() => setChannel(c.id)}
              className={`badge ${channel === c.id ? "bg-accent text-white" : "bg-gray-100 text-gray-700"}`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500">Voice:</span>
          {VOICES.map((v) => (
            <button
              key={v.id}
              onClick={() => setVoice(v.id)}
              className={`badge ${voice === v.id ? "bg-accent text-white" : "bg-gray-100 text-gray-700"}`}
            >
              {v.label}
            </button>
          ))}
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-500">Prospect — profile URL (we&apos;ll try to scrape)</label>
          <input className="w-full text-sm border border-gray-200 rounded p-2"
                 placeholder="https://www.linkedin.com/in/…" value={prospectUrl}
                 onChange={(e) => setProspectUrl(e.target.value)} />
          <label className="text-xs font-medium text-gray-500">…or paste who they are (role, company, industry, anything relevant)</label>
          <textarea className="w-full text-sm border border-gray-200 rounded p-2" rows={2}
                    placeholder="e.g. Head of Ops at a mid-size personal-injury law firm; posts about case backlog"
                    value={prospectText} onChange={(e) => setProspectText(e.target.value)} />
        </div>

        {cfg.needsThread ? (
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">Conversation so far (most recent last)</label>
            <textarea className="w-full text-sm border border-gray-200 rounded p-2 font-mono" rows={5}
                      placeholder={"Them: ...\nYou: ...\nThem: ..."} value={threadText}
                      onChange={(e) => setThreadText(e.target.value)} />
          </div>
        ) : (
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">
              {cfg.needsPost ? "The post to react to — URL or text" : "Optional: a recent post/article of theirs — URL or text"}
            </label>
            <input className="w-full text-sm border border-gray-200 rounded p-2"
                   placeholder="https://www.linkedin.com/posts/…" value={postUrl}
                   onChange={(e) => setPostUrl(e.target.value)} />
            <textarea className="w-full text-sm border border-gray-200 rounded p-2" rows={3}
                      placeholder="…or paste the post text here" value={postText}
                      onChange={(e) => setPostText(e.target.value)} />
          </div>
        )}

        <button className="btn btn-ok" disabled={pending} onClick={run}>
          {pending ? "Generating…" : "Generate 3 variants"}
        </button>
        {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>}
      </div>

      {result?.variants?.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs text-gray-500">
            {result.label} · {VOICES.find((v) => v.id === result.voice)?.label || "AI Guy"} voice
            {result.used_scrape?.prospect && " · scraped prospect"}
            {result.used_scrape?.post && " · scraped post"}
          </div>
          {result.variants.map((v: Variant, i: number) => (
            <div key={i} className="card space-y-2">
              {isEmail && v.subject && (
                <div className="text-sm font-semibold">
                  Subject: {v.subject} <CopyBtn value={v.subject} />
                </div>
              )}
              <p className="text-sm whitespace-pre-wrap">{v.text}</p>
              <div className="flex items-center gap-2">
                <CopyBtn value={isEmail && v.subject ? `${v.subject}\n\n${v.text}` : v.text} />
                {typeof v.chars === "number" && <span className="text-[10px] text-gray-400">{v.chars} chars</span>}
                {v.flags?.map((f, j) => (
                  <span key={j} className="text-[10px] text-amber-700 bg-amber-50 rounded px-1">⚠ {f}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
