"use client";
import { useTransition } from "react";
import { markPostEngaged } from "@/app/actions";

// One "post to comment on" — an influencer/keyword post with a pre-drafted
// comment in your voice. (Groups sunset; Comments tab is influencer posts only.)
export type CommentTarget = {
  id: string;
  kind: "influencer";
  source: string; // person name
  sourceUrl?: string | null;
  body: string;
  postUrl?: string | null;
  score?: number | null;
  action?: string | null;
  comment?: string | null;
};

export function CommentCard({ t }: { t: CommentTarget }) {
  const [pending, start] = useTransition();
  const mark = (status: string) => start(() => markPostEngaged(t.id, status));

  return (
    <div className={`card !p-3 ${pending ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="badge text-[10px] bg-blue-100 text-blue-800">person</span>
        <span className="text-sm font-medium text-gray-900 truncate">{t.source}</span>
        {typeof t.score === "number" && (
          <span className="text-xs font-mono text-gray-500 shrink-0">⚡{t.score}</span>
        )}
        {t.postUrl && (
          <a href={t.postUrl} target="_blank" rel="noreferrer" className="ml-auto text-xs text-accent hover:underline shrink-0">
            open post ↗
          </a>
        )}
      </div>

      <p className="text-xs text-gray-600 line-clamp-3 mb-2">{t.body}</p>

      {t.comment && (
        <div className="rounded bg-gray-50 border border-gray-200 p-2 mb-2">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-0.5">
            Suggested comment (your voice)
          </div>
          <p className="text-sm text-gray-800">{t.comment}</p>
        </div>
      )}

      <div className="flex gap-1">
        {t.postUrl && (
          <a
            href={t.postUrl}
            target="_blank"
            rel="noreferrer"
            className="px-2 py-1 text-[11px] rounded bg-accent text-white"
          >
            Open & comment ↗
          </a>
        )}
        <button
          disabled={pending}
          onClick={() => mark("commented")}
          className="px-2 py-1 text-[11px] rounded border border-green-300 text-green-700 hover:bg-green-50 disabled:opacity-50"
        >
          ✓ Commented
        </button>
        <button
          disabled={pending}
          onClick={() => mark("dismissed")}
          className="px-2 py-1 text-[11px] rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          Skip
        </button>
      </div>
    </div>
  );
}
