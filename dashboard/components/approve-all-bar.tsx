"use client";
import { useTransition } from "react";
import { approveAll } from "@/app/actions";

export function ApproveAllBar({ ids, count }: { ids: string[]; count: number }) {
  const [pending, start] = useTransition();
  if (count === 0) return null;
  return (
    <button
      disabled={pending}
      onClick={() => start(async () => { await approveAll(ids); })}
      className="btn btn-primary w-full disabled:opacity-50"
    >
      {pending ? "Approving…" : `Approve all ${count} drafts`}
    </button>
  );
}
