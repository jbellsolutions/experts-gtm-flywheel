"use client";
import { addManualIdea } from "@/app/actions";
import { useTransition, useState } from "react";

export function AddIdeaForm() {
  const [text, setText] = useState("");
  const [pending, start] = useTransition();

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const value = text.trim();
        if (!value) return;
        start(async () => {
          await addManualIdea(value);
          setText("");
        });
      }}
      className="rounded-lg border border-gray-200 p-3 bg-gray-50 space-y-2"
    >
      <label className="block text-xs font-semibold text-gray-700">
        Drop an idea (text, YouTube link, URL, or all three)
      </label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder="e.g. The dumbest objection I heard this week — and the 1-line response that closes it. Reference: https://youtu.be/..."
        className="w-full text-sm rounded border border-gray-300 p-2 focus:outline-none focus:ring-2 focus:ring-accent"
      />
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={pending || !text.trim()}
          className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:opacity-90 disabled:opacity-50"
        >
          {pending ? "Queuing…" : "Queue idea (priority 80)"}
        </button>
      </div>
      <p className="text-[11px] text-gray-500">
        Manual ideas land at priority 80. Slack DMs to the bot land at 90 (highest)
        and any URL is automatically transcribed/scraped before queuing.
      </p>
    </form>
  );
}
