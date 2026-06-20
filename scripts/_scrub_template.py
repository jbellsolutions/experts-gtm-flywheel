#!/usr/bin/env python3
"""Scrub brand + secret residue out of the template tree, then leak-check.

Used by scripts/sync_from_internal.sh after pulling system code from an internal
brand deployment (e.g. the AI Guy build). Also runnable standalone:

    python scripts/_scrub_template.py            # scrub + check, in place
    python scripts/_scrub_template.py --check     # check only (CI gate; non-zero on leak)

It does NOT touch the deliberately-templated brand files (brand_voice.py, voices.py,
voice_banks/, leadgen-offers.ts, the setup scripts, etc.) — those are owned by the
template and the onboarding assistant. It scrubs everything else: replaces known
hard-coded IDs/URLs with placeholders and rewrites brand-person phrasing generically.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = (".py", ".ts", ".tsx", ".js", ".md", ".json", ".sql", ".yaml", ".yml", ".txt", ".html")
SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__"}

# Files the template owns — never auto-scrub/overwrite (they're intentionally generic).
PROTECTED = {
    "agents/content_flywheel/repurposer/brand_voice.py",
    "agents/content_flywheel/repurposer/voices.py",
    "dashboard/lib/leadgen-offers.ts",
    "dashboard/app/leads/page.tsx",
    "scripts/smartlead_setup.py",
    "scripts/airtable_setup.py",
    "scripts/_scrub_template.py",
    "CLAUDE.md", "AGENTS.md", "README.md",
}
PROTECTED_PREFIXES = ("agents/content_flywheel/repurposer/voice_banks/", "docs/")

# Exact ID/URL/email → placeholder. Extend with any brand-specific values you add.
IDS = {
    "dashboard-production-5e9a.up.railway.app": "your-dashboard.up.railway.app",
    "usingaitoscale.com": "yourdomain.com",
    "jbellsolutions/ai-guy-flywheel": "your-org/experts-gtm-flywheel",
    "jbellsolutions/speakeragent-flywheel": "your-org/experts-gtm-flywheel",
    "michal@archdesk.com": "jane@acme.com", "Archdesk": "Acme",
}
# Regex IDs (Airtable base, SmartLead campaign, Slack/Unipile ids).
ID_PATTERNS = [
    (re.compile(r"app[A-Za-z0-9]{14}"), "appXXXXXXXXXXXXXX"),
    (re.compile(r"\bU0[A-Z0-9]{8,9}\b"), "U0XXXXXXXXX"),
]
# Brand-person phrasing → generic (ordered: specific first, bare token last).
PHRASING = [
    ("Justin's", "your"), ("Justin approves", "you approve"),
    ("Justin reviews", "you review"), ("Justin sends", "you send"),
    ("Justin tweaked then approved", "you tweaked then approved"),
    ("so Justin", "so you"), ("while Justin", "while you"), ("Justin —", "you —"),
    ("(Xander)", "(a teammate)"),
    ("The AI Guy", "Your brand"), ("the AI Guy", "your brand"), ("AI Guy", "your brand"),
    ("AI Integraterz", "your offer"), ("Capstone", "client win"),
    ("Justin", "you"),
]
# Anything matching these in the (non-protected) tree after scrub = a leak.
LEAK = re.compile(
    r"justin|the ai guy|ai integraterz|capstone|comptia|usingaitoscale|jbellsolutions|"
    r"apprZDW|appDPSR|352010|352088|GHTmdj|archdesk|sk-ant-[A-Za-z0-9]|xox[bp]-[A-Za-z0-9]|"
    r"\bpat[A-Za-z0-9]{14}", re.I)


def _files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(EXTS):
                continue
            rel = os.path.relpath(os.path.join(root, fn), ROOT)
            if rel in PROTECTED or rel.startswith(PROTECTED_PREFIXES):
                continue
            yield rel


def scrub() -> int:
    changed = 0
    for rel in _files():
        p = os.path.join(ROOT, rel)
        t = open(p, encoding="utf-8").read(); o = t
        for a, b in IDS.items():
            t = t.replace(a, b)
        for rx, repl in ID_PATTERNS:
            t = rx.sub(repl, t)
        for a, b in PHRASING:
            t = t.replace(a, b)
        if t != o:
            open(p, "w", encoding="utf-8").write(t); changed += 1
    print(f"scrubbed {changed} file(s)")
    return changed


def check() -> int:
    leaks = []
    for rel in _files():
        for i, line in enumerate(open(os.path.join(ROOT, rel), encoding="utf-8"), 1):
            if LEAK.search(line):
                leaks.append(f"{rel}:{i}: {line.strip()[:100]}")
    if leaks:
        print("LEAK CHECK FAILED — brand/secret residue found:")
        for l in leaks[:50]:
            print("  " + l)
        return 1
    print("leak check clean ✓ (no brand/secret residue outside protected template files)")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    scrub()
    sys.exit(check())
