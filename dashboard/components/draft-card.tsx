"use client";
import { useState, useTransition } from "react";
import { approveDraft, rejectDraft, snoozeDraft, retryDraft, rerunDraft, deleteDraft } from "@/app/actions";
import { fmtTime } from "@/lib/utils";

export function DraftCard({ draft }: { draft: any }) {
  const [body, setBody] = useState(draft.body);
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();
  const edited = body !== draft.body;

  const overdue =
    draft.status === "pending" &&
    draft.scheduled_for &&
    new Date(draft.scheduled_for) < new Date();
  const pillarBadge = draft.pillar === "1"
    ? "bg-blue-100 text-blue-800"
    : draft.pillar === "2"
    ? "bg-purple-100 text-purple-800"
    : "bg-gray-100 text-gray-800";

  const VOICE_META: Record<string, { label: string; cls: string }> = {
    ai_guy: { label: "AI Guy", cls: "bg-sky-100 text-sky-800" },
    human_loop: { label: "Human-Loop", cls: "bg-emerald-100 text-emerald-800" },
    ai_reality: { label: "AI-Reality", cls: "bg-rose-100 text-rose-800" },
  };
  const voice = draft.metadata?.voice ? VOICE_META[draft.metadata.voice] : null;

  return (
    <div className="card">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left flex items-center justify-between gap-2"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="badge bg-gray-900 text-white">{draft.platform}</span>
          {voice ? (
            <span className={`badge ${voice.cls}`}>{voice.label}</span>
          ) : (
            <span className={`badge ${pillarBadge}`}>P{draft.pillar}</span>
          )}
          <span className="text-xs text-gray-500 truncate">{draft.format}</span>
          {draft.platform === "linkedin" && ["post","article","newsletter"].includes(draft.format) && draft.metadata?.visual && (
            <span className="badge bg-indigo-100 text-indigo-800 text-[10px]">
              {draft.metadata.visual.type === "carousel"
                ? `carousel · ${draft.metadata.visual.slide_urls?.length ?? 0}`
                : draft.metadata.visual.type === "video"
                ? `video · ${draft.metadata.visual.mode ?? "motion"}`
                : "image"}
            </span>
          )}
          {overdue && (
            <span className="badge bg-amber-100 text-amber-800 text-[10px]">overdue</span>
          )}
          {draft.status === "failed" && (
            <span className="badge bg-red-100 text-red-800 text-[10px]">failed</span>
          )}
        </div>
        <span className={`text-xs shrink-0 ${overdue ? "text-amber-700" : "text-gray-500"}`}>
          {fmtTime(draft.scheduled_for)}
        </span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={Math.min(20, Math.max(6, body.split("\n").length + 1))}
            className="w-full text-sm border border-gray-200 rounded p-2 font-mono resize-y focus:outline-none focus:ring-2 focus:ring-accent"
          />
          {draft.metadata?.qa_issues?.length > 0 && (
            <div className="text-xs text-warn bg-amber-50 border border-amber-200 rounded p-2">
              ⚠ QA flagged: {draft.metadata.qa_issues.join("; ")}
            </div>
          )}
          {draft.status === "failed" && draft.metadata?.error && (
            <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2 font-mono whitespace-pre-wrap">
              ⚠ Last failure: {String(draft.metadata.error).slice(0, 300)}
            </div>
          )}

          {draft.platform === "linkedin" && ["post","article","newsletter"].includes(draft.format) && (
            <div className="border border-gray-200 rounded p-2 bg-gray-50">
              {draft.metadata?.visual?.status === "rendered" ? (
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">
                    {draft.metadata.visual.type === "carousel"
                      ? `Carousel — ${draft.metadata.visual.slide_urls?.length ?? 0} slides (swipe on LinkedIn)`
                      : draft.metadata.visual.type === "video"
                      ? `Motion video — ${draft.metadata.visual.mode ?? "motion"}`
                      : "Single image"}
                  </div>
                  {draft.metadata.visual.format_reason && (
                    <div className="text-[11px] text-gray-600 mb-2">
                      <span className="font-medium text-indigo-700">Orchestrator’s call:</span>{" "}
                      {draft.metadata.visual.format_reason}
                      {draft.metadata.visual.motion_reason && (
                        <> {" — "}{draft.metadata.visual.motion_reason}</>
                      )}
                    </div>
                  )}
                  {draft.metadata.visual.type === "carousel" ? (
                    <div className="flex gap-2 overflow-x-auto pb-1">
                      {(draft.metadata.visual.slide_urls ?? []).map((u: string, i: number) => (
                        <a key={i} href={u} target="_blank" rel="noreferrer" className="shrink-0">
                          <img src={u} alt={`Slide ${i + 1}`} className="h-44 rounded border border-gray-200" />
                        </a>
                      ))}
                    </div>
                  ) : draft.metadata.visual.type === "video" && draft.metadata.visual.video_url ? (
                    <video src={draft.metadata.visual.video_url} controls playsInline
                           className="h-72 rounded border border-gray-200 bg-black" />
                  ) : (
                    <a href={draft.metadata.visual.image_url} target="_blank" rel="noreferrer">
                      <img src={draft.metadata.visual.image_url} alt="Visual" className="h-56 rounded border border-gray-200" />
                    </a>
                  )}
                </div>
              ) : draft.metadata?.visual?.type === "video" && draft.metadata?.visual?.status === "generating" ? (
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">
                    Motion video — {draft.metadata.visual.mode ?? "motion"} · rendering…
                  </div>
                  {draft.metadata.visual.anchor_image_url && (
                    <a href={draft.metadata.visual.anchor_image_url} target="_blank" rel="noreferrer">
                      <img src={draft.metadata.visual.anchor_image_url} alt="Anchor card"
                           className="h-56 rounded border border-gray-200 opacity-80" />
                    </a>
                  )}
                  <div className="text-xs text-gray-500 italic mt-1">Animating the hero (~a few min). Static card above ships if the clip isn’t ready.</div>
                </div>
              ) : draft.metadata?.visual_error ? (
                <div className="text-xs text-red-700">⚠ Visual failed: {String(draft.metadata.visual_error).slice(0, 160)} — post will go out text-only.</div>
              ) : (
                <div className="text-xs text-gray-500 italic">Generating visual… (carousel, image, or video, ~a few min)</div>
              )}
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            {draft.status === "failed" ? (
              <button
                disabled={pending}
                onClick={() => start(async () => { await retryDraft(draft.id); })}
                className="btn btn-ok flex-1"
              >
                {pending ? "…" : "Retry publish"}
              </button>
            ) : (
              <button
                disabled={pending}
                onClick={() => start(async () => {
                  await approveDraft(draft.id, edited ? body : undefined);
                })}
                className="btn btn-ok flex-1"
              >
                {pending ? "…" : edited ? "Save & Approve" : "Approve"}
              </button>
            )}
            <button
              disabled={pending}
              onClick={() => start(async () => { await rejectDraft(draft.id); })}
              className="btn btn-ghost text-bad"
            >
              Reject
            </button>
            <button
              disabled={pending}
              onClick={() => start(async () => { await snoozeDraft(draft.id); })}
              className="btn btn-ghost"
            >
              Snooze 1d
            </button>
            <button
              disabled={pending}
              title="Regenerate this post in its voice with a fresh trend + industry"
              onClick={() => start(async () => { await rerunDraft(draft.id); })}
              className="btn btn-ghost"
            >
              {pending ? "…" : "↻ Rerun"}
            </button>
            <button
              disabled={pending}
              onClick={() => {
                if (confirm("Delete this draft permanently?"))
                  start(async () => { await deleteDraft(draft.id); });
              }}
              className="btn btn-ghost text-bad"
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {!open && (
        <p className="text-sm text-gray-600 mt-1 line-clamp-2">{draft.body}</p>
      )}
    </div>
  );
}
