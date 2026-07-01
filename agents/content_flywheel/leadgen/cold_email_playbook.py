"""Cold-email playbook — the copy rules + campaign-angle frameworks the Hermes
cold-email agent works from.

Distilled from the Single Brain cold-email system (a multi-agent SmartLead pipeline)
into a brand-free, portable form: any offer / voice can use it. The Hermes agent injects
VOICE_RULES into its system prompt and picks a FRAMEWORK angle from the target + the
business info; the per-lead drafter (email_draft) also folds VOICE_RULES into email 1.
"""
from __future__ import annotations

# The non-negotiable voice rules for every cold email (email 1 + the follow-ups).
VOICE_RULES = """\
COLD-EMAIL VOICE RULES (apply to every email):
- Frame: a cold email is the START of a conversation, not a pitch. Sound like a real
  person who built something, not a vendor running a sequence.
- Length: email 1 <= 125 words; follow-ups <= 100 words. Short beats clever.
- NO links in the first 1-3 emails. Links only after the prospect replies and asks.
- Open on the SUBSTANCE of what they do / said — never "I saw your post/comment".
- Threading: follow-ups keep the SAME subject as email 1 (re: ...). No new subjects.
- No fake urgency, no fake timeframes, no "free" in the hook, no program/course talk.
- No AI-hype language. Plain, specific, human.
- CTA is reply-based and low-friction ("worth a quick reply?", "open to a look?") —
  never a demand, never a calendar link in the cold email.
- Sign off as a person. One clear ask per email.
"""

# Campaign-angle frameworks (generalized from the Single Brain angle bank). Each is a
# hook the agent anchors a campaign to, filled with the offer + the target's specifics.
FRAMEWORKS = [
    {"key": "silent_bleed", "name": "Silent Bleed",
     "angle": "Money quietly leaking from a gap they haven't fixed (missed follow-ups, "
              "dropped leads, manual work) — name the leak, offer to stop it."},
    {"key": "want_a_human", "name": "People Want a Human",
     "angle": "Their customers/prospects are drowning in automated noise and want a real "
              "person — position the offer as the human in the loop."},
    {"key": "everyone_has_x", "name": "Everyone Has X, Nobody Has This",
     "angle": "The thing everyone now has (a tool, AI, ads) is commoditized — the edge is "
              "the thing they DON'T have, which the offer provides."},
    {"key": "quiet_channel", "name": "The Quiet Channel",
     "angle": "A channel/asset they own is underused (old list, past customers, inbound) — "
              "reactivate it instead of buying more top-of-funnel."},
    {"key": "build_not_buy", "name": "Built, Not Bought",
     "angle": "They've bought tools/courses that still need someone to implement — the "
              "offer is the person who actually builds and ships it."},
]

FRAMEWORK_KEYS = [f["key"] for f in FRAMEWORKS]


def framework(key: str) -> dict | None:
    return next((f for f in FRAMEWORKS if f["key"] == key), None)


def frameworks_brief() -> str:
    """One line per framework — for the agent's system prompt / a picker."""
    return "\n".join(f"- {f['name']} ({f['key']}): {f['angle']}" for f in FRAMEWORKS)
