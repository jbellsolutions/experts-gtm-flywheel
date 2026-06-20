"use client";
import { useState, useTransition } from "react";
import { toggleChecklistItem } from "@/app/actions";

export function ChecklistItem({ date, item }: { date: string; item: any }) {
  const [pending, start] = useTransition();
  const [open, setOpen] = useState(false);
  const hasDetail = !!(item.description || item.target);

  return (
    <li>
      <div className="flex items-start gap-3">
        <button
          disabled={pending}
          onClick={() =>
            start(async () => {
              await toggleChecklistItem(date, item.id, !item.completed);
            })
          }
          className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center transition shrink-0 ${
            item.completed
              ? "bg-ok border-ok text-white"
              : "border-gray-300 hover:border-accent"
          }`}
        >
          {item.completed && (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>
        <div className="flex-1 min-w-0">
          <button
            onClick={() => setOpen(!open)}
            className="text-left w-full"
            disabled={!hasDetail}
          >
            <span className={`text-sm ${item.completed ? "line-through text-gray-400" : "text-gray-900"}`}>
              {item.label}
            </span>
            {item.target && (
              <span className="block text-xs text-gray-500 mt-0.5">→ {item.target}</span>
            )}
          </button>
          {open && item.description && (
            <p className="mt-2 text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded p-2 leading-relaxed">
              {item.description}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}
