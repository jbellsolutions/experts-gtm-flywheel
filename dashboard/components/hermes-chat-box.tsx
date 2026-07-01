"use client";
import { useState, useTransition } from "react";

type Msg = { role: "user" | "assistant"; content: string };
type Lead = { name?: string; email?: string; company?: string; linkedin_url?: string; headline?: string };

const GREETING =
  "Hi — I'm Hermes. I'll build you a cold-email campaign. Tell me who you want to reach " +
  "(paste a LinkedIn post URL and I'll pull its commenters, or upload a list), which offer " +
  "you're selling, and in which voice. I'll ask a couple quick questions, then set up the " +
  "SmartLead campaign. Nothing sends until you add inboxes and hit START — leads land in " +
  "Airtable for you to review first.";

// Parse pasted text / a CSV into leads. CSV (comma + a header row) maps columns; otherwise
// each line is one token (a LinkedIn URL, an email, or a name).
function parseLeads(text: string): Lead[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return [];
  if (lines[0].includes(",") && /name|email|linkedin|company/i.test(lines[0])) {
    const headers = lines[0].split(",").map((h) => h.trim().toLowerCase());
    return lines
      .slice(1)
      .map((ln) => {
        const cols = ln.split(",");
        const row: Record<string, string> = {};
        headers.forEach((h, i) => (row[h] = (cols[i] || "").trim()));
        return {
          name: row["name"] || row["full name"] || "",
          email: row["email"] || "",
          company: row["company"] || row["company name"] || "",
          linkedin_url: row["linkedin"] || row["linkedin url"] || row["url"] || "",
          headline: row["headline"] || row["title"] || "",
        };
      })
      .filter((l) => l.email || l.linkedin_url || l.name);
  }
  return lines.map((ln) => {
    if (ln.includes("linkedin.com")) return { linkedin_url: ln };
    if (ln.includes("@")) return { email: ln };
    return { name: ln };
  });
}

export function HermesChatBox({
  businessInfo,
  offers,
  voices,
}: {
  businessInfo: string;
  offers: { slug: string; label: string }[];
  voices: { id: string; label: string }[];
}) {
  const [messages, setMessages] = useState<Msg[]>([{ role: "assistant", content: GREETING }]);
  const [input, setInput] = useState("");
  const [pending, start] = useTransition();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadText, setUploadText] = useState("");
  const [done, setDone] = useState<any>(null);
  const [error, setError] = useState("");

  function addPasted() {
    const parsed = parseLeads(uploadText);
    if (parsed.length) {
      setLeads(parsed);
      setUploadText("");
      setShowUpload(false);
    }
  }
  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const parsed = parseLeads(await f.text());
    if (parsed.length) {
      setLeads(parsed);
      setShowUpload(false);
    }
  }

  function send() {
    const text = input.trim();
    if (!text || pending) return;
    setError("");
    setInput("");
    const next: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    start(async () => {
      try {
        const r = await fetch("/api/hermes/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: next,
            context: {
              business_info: businessInfo,
              offers: offers.map((o) => ({ label: o.label })),
              voices: voices.map((v) => ({ label: v.label })),
              uploaded_leads: leads,
            },
          }),
        });
        const data = await r.json();
        if (data.error) {
          setError(data.error);
          return;
        }
        if (data.reply) setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
        if (data.enqueued) setDone(data);
      } catch (e: any) {
        setError(String(e?.message || e));
      }
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button className="btn btn-ghost" onClick={() => setShowUpload((s) => !s)}>
          {leads.length ? `📄 ${leads.length} leads loaded` : "⬆ Upload a lead list"}
        </button>
        {leads.length > 0 && (
          <button className="text-gray-400 hover:text-red-600" onClick={() => setLeads([])}>
            clear
          </button>
        )}
        <span className="text-gray-400">…or just paste a LinkedIn post URL in the chat</span>
      </div>

      {showUpload && (
        <div className="card space-y-2">
          <input type="file" accept=".csv,.txt" onChange={onFile} className="text-xs" />
          <div className="text-[11px] text-gray-400">
            …or paste LinkedIn URLs / emails (one per line), or a CSV with a header row
          </div>
          <textarea
            className="w-full text-sm border border-gray-200 rounded p-2 font-mono"
            rows={4}
            value={uploadText}
            onChange={(e) => setUploadText(e.target.value)}
            placeholder={"https://www.linkedin.com/in/…\njane@acme.com\n…or: name,email,company,linkedin"}
          />
          <button className="btn btn-ok text-xs" onClick={addPasted}>
            Add {parseLeads(uploadText).length || ""} leads
          </button>
        </div>
      )}

      <div className="card space-y-3 max-h-[440px] overflow-y-auto">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div
              className={`inline-block text-sm rounded-lg px-3 py-2 whitespace-pre-wrap ${
                m.role === "user" ? "bg-accent text-white" : "bg-gray-100 text-gray-800"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {pending && <div className="text-xs text-gray-400">Hermes is thinking…</div>}
      </div>

      {done?.enqueued && (
        <div className="card !bg-green-50 border-green-200 text-sm space-y-1">
          <div className="font-semibold text-green-800">
            ✓ Campaign queued: {done.campaign?.campaign_name}
          </div>
          <div className="text-green-700 text-xs">
            The worker is creating the SmartLead campaign (unstarted) and pulling the leads into your
            Airtable Contacts. Approve the ones you want → they enrich, draft a custom email, and push
            to the campaign. <b>Nothing sends until you add inboxes and hit START in SmartLead.</b>
          </div>
        </div>
      )}
      {error && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>
      )}

      <div className="flex gap-2">
        <textarea
          className="flex-1 text-sm border border-gray-200 rounded p-2"
          rows={2}
          placeholder="Message Hermes… (e.g. 'Pull commenters from https://linkedin.com/posts/… — sell your offer in your brand voice')"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
        />
        <button className="btn btn-ok" disabled={pending} onClick={send}>
          Send
        </button>
      </div>
      <div className="text-[10px] text-gray-400">⌘/Ctrl+Enter to send</div>
    </div>
  );
}
