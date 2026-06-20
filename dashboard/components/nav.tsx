"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/today",       label: "Today" },
  { href: "/ideas",       label: "Ideas" },
  { href: "/drafts",      label: "Drafts" },
  { href: "/newsletter",  label: "Newsletter" },
  { href: "/comments",    label: "Comments" },
  { href: "/prospecting", label: "Prospecting" },
  { href: "/leads",       label: "Leads" },
  { href: "/guide",       label: "Guide" },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav className="flex gap-1 border-b border-gray-200 overflow-x-auto">
      {TABS.map((t) => {
        const active = path === t.href || (path === "/" && t.href === "/today");
        return (
          <Link
            key={t.href}
            href={t.href}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition whitespace-nowrap",
              active
                ? "border-accent text-accent"
                : "border-transparent text-gray-500 hover:text-gray-900"
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
