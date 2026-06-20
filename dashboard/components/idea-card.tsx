"use client";
import { boostIdea, dismissIdea, useIdeaNow } from "@/app/actions";
import { useTransition } from "react";

type Idea = {
  id: string;
  source: string;
  content: string;
  priority: number;
  parsed_content?: any;
  metadata?: any;
  created_at: string;
};

export function IdeaCard({ idea, sourceLabel }: { idea: Idea; sourceLabel: string }) {
  const [pending, start] = useTransition();
  const parsed = idea.parsed_content || {};
  const hasUrl = parsed.kind === "youtube" || parsed.kind === "web";
  const url = parsed.url;

  return (
    <div className="rounded-lg border border-gray-200 p-3 bg-white">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="font-medium text-gray-700">{sourceLabel}</span>
          <span>•</span>
          <span title="Priority (0-100)">⚡ {idea.priority}</span>
          {hasUrl && (
            <>
              <span>•</span>
              <a href={url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                {parsed.kind === "youtube" ? "▶ YouTube" : "🔗 link"}
              </a>
            </>
          )}
          {parsed.error && (
            <span className="text-red-600" title={parsed.error}>⚠ parse error</span>
          )}
        </div>
        <div className="text-[10px] text-gray-400">
          {new Date(idea.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
        </div>
      </div>

      <p className="text-sm text-gray-900 whitespace-pre-wrap mb-2">{idea.content}</p>

      <div className="flex flex-wrap gap-1">
        <button
          disabled={pending}
          onClick={() => start(() => useIdeaNow(idea.id))}
          className="px-2 py-1 text-xs rounded bg-accent text-white hover:opacity-90 disabled:opacity-50"
        >
          Use now
        </button>
        <button
          disabled={pending}
          onClick={() => start(() => boostIdea(idea.id, 10))}
          className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
        >
          + Boost
        </button>
        <button
          disabled={pending}
          onClick={() => start(() => boostIdea(idea.id, -10))}
          className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
        >
          − Demote
        </button>
        <button
          disabled={pending}
          onClick={() => start(() => dismissIdea(idea.id))}
          className="px-2 py-1 text-xs rounded border border-gray-300 text-gray-600 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
