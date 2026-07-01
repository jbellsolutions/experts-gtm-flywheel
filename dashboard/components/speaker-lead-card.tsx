"use client";
import { useState, useTransition } from "react";
import { actionSpeakerLead, actionSpeakerSaved, actionSpeakerRefresh } from "@/app/actions";

type Pod = { id: string; [field: string]: any };
const f = (p: Pod, k: string): string => (p[k] ?? "") as string;

const TRIAGE: Record<string, string> = {
  GREEN: "bg-green-500",
  YELLOW: "bg-yellow-400",
  RED: "bg-red-500",
};
const STATUSES = ["New", "Contacted", "Replied", "Booked", "Passed"];

// A SpeakerAgent podcast lead — a show to pitch yourself onto. Raw podcasts have no
// contact/email draft until "Generate pitch" (refresh) enriches the host + drafts the email.
export function SpeakerLeadCard({ lead }: { lead: Pod }) {
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();

  const show = f(lead, "Podcast Name") || "Podcast";
  const host = f(lead, "Host Name");
  const triage = f(lead, "Lead Triage");
  const score = lead["Match Score"];
  const saved = Boolean(lead["Saved"]);
  const email = f(lead, "Contact Email");
  const li = f(lead, "Contact LinkedIn");
  const site = f(lead, "Podcast URL") || f(lead, "Booking URL") || f(lead, "Guest Form URL");
  const subject = f(lead, "Email Subject");
  const body = f(lead, "Email Draft");
  const gmail = email
    ? `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(email)}` +
      `&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    : "";

  return (
    <div className={`card !p-3 flex flex-col ${pending ? "opacity-50" : ""}`}>
      <button onClick={() => setOpen(!open)} className="text-left w-full">
        <div className="flex items-center gap-1.5 mb-1">
          {triage && (
            <span className={`w-2 h-2 rounded-full shrink-0 ${TRIAGE[triage] || "bg-gray-300"}`} />
          )}
          <span className="text-sm font-semibold text-gray-900 truncate">{show}</span>
          {saved && <span className="text-pink-500 shrink-0" title="saved">♥</span>}
          {typeof score === "number" && (
            <span className="ml-auto text-[11px] font-mono text-gray-400 shrink-0">
              {Math.round(score)}
            </span>
          )}
        </div>
        {host && <div className="text-xs text-gray-500 truncate">{host}</div>}
        {f(lead, "Best Topic") && (
          <div className="text-[10px] uppercase tracking-wide text-gray-400 mt-0.5 truncate">
            {f(lead, "Best Topic")}
          </div>
        )}
      </button>

      {open && (
        <div className="mt-2 pt-2 border-t border-gray-100 space-y-2 text-xs">
          {f(lead, "The Hook") && (
            <p className="text-gray-700">
              <b>Hook:</b> {f(lead, "The Hook")}
            </p>
          )}
          {f(lead, "Reach Estimate") && (
            <p className="text-gray-500">Reach: {f(lead, "Reach Estimate")}</p>
          )}
          {body ? (
            <div className="rounded bg-gray-50 border border-gray-200 p-2">
              <div className="font-medium text-gray-800 mb-0.5">{subject || "(drafted email)"}</div>
              <p className="text-gray-600 whitespace-pre-wrap line-clamp-6">{body}</p>
            </div>
          ) : (
            <p className="text-[11px] text-amber-600">
              No pitch yet — hit <b>Generate pitch</b> to enrich the host + draft the email.
            </p>
          )}
          <div className="flex flex-wrap gap-1">
            {gmail && (
              <a href={gmail} target="_blank" rel="noreferrer"
                className="px-2 py-1 rounded bg-green-600 text-white text-[11px]">
                ✉ Send email
              </a>
            )}
            <button
              disabled={pending}
              onClick={() => start(() => actionSpeakerRefresh(lead.id))}
              className="px-2 py-1 rounded border border-violet-300 text-violet-700 text-[11px] disabled:opacity-50"
            >
              ✨ Generate pitch
            </button>
            {li && (
              <a href={li} target="_blank" rel="noreferrer"
                className="px-2 py-1 rounded border border-blue-300 text-blue-700 text-[11px]">
                in LinkedIn
              </a>
            )}
            {site && (
              <a href={site} target="_blank" rel="noreferrer"
                className="px-2 py-1 rounded border border-gray-300 text-gray-600 text-[11px]">
                ↗ Show
              </a>
            )}
            <button
              disabled={pending}
              onClick={() => start(() => actionSpeakerSaved(lead.id, !saved))}
              className={`px-2 py-1 rounded border text-[11px] disabled:opacity-50 ${
                saved ? "border-pink-300 text-pink-600" : "border-gray-300 text-gray-500"
              }`}
            >
              {saved ? "♥ Saved" : "♡ Save"}
            </button>
          </div>
          <label className="flex items-center gap-1 text-[11px] text-gray-500">
            Status
            <select
              defaultValue={STATUSES.includes(f(lead, "Lead Status")) ? f(lead, "Lead Status") : "New"}
              disabled={pending}
              onChange={(e) => start(() => actionSpeakerLead(lead.id, e.target.value))}
              className="border border-gray-200 rounded px-1 py-0.5 text-[11px]"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
    </div>
  );
}
