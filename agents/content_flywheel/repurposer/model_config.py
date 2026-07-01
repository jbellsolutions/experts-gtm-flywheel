"""Model dispatch — single source of truth for which model handles which task.

Swap any value, redeploy. No code changes anywhere else.

Each entry: (provider, model_name, max_tokens). Provider is "anthropic" or
"openai". Pricing is captured in COST_PER_MTOK for back-of-the-envelope cost
reporting in the weekly digest.

Honest defaults:
- Sonnet 4.5 for voice-critical content (LinkedIn, Substack, Medium, newsletter).
- Haiku 4.5 for inbound reply suggestions.
- Browser Use driver: Sonnet 4.6 (set in browser_runner via BU Cloud SDK).
- Heuristic-only for pillar classification + lead scoring (no LLM).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    provider: str    # "anthropic" | "openai"
    name: str        # API model id
    max_tokens: int  # output cap


# ── The dispatch table ───────────────────────────────────────────────────────

MODELS: dict[str, ModelSpec] = {
    # Long-form, voice-critical
    "linkedin_post":      ModelSpec("anthropic", "claude-sonnet-4-5", 1500),
    "linkedin_article":   ModelSpec("anthropic", "claude-sonnet-4-5", 4000),
    "substack_post":      ModelSpec("anthropic", "claude-sonnet-4-5", 6000),
    "medium_article":     ModelSpec("anthropic", "claude-sonnet-4-5", 4000),
    "newsletter_section": ModelSpec("anthropic", "claude-sonnet-4-5", 1500),

    # Editorial team — 3-stage long-form pipeline (architect -> drafter -> editor).
    # Routes through editorial.write_long_form() for {linkedin/article,
    # substack/post, medium/article, newsletter/section}. LinkedIn posts
    # stay single-shot via linkedin_post above.
    "editorial_architect": ModelSpec("anthropic", "claude-sonnet-4-5", 1500),
    "editorial_drafter":   ModelSpec("anthropic", "claude-sonnet-4-5", 6000),
    "editorial_editor":    ModelSpec("anthropic", "claude-sonnet-4-5", 6000),

    # Inbound / replies
    "inbox_reply":        ModelSpec("anthropic", "claude-haiku-4-5", 500),

    # Browser Use agent
    "browser_use":        ModelSpec("anthropic", "claude-sonnet-4-5", 4000),

    # Voice tuning analysis (Sunday auto-promote job)
    "voice_tune":         ModelSpec("anthropic", "claude-sonnet-4-5", 4000),

    # Idea queue: brand-voice fallback suggester (when queue is low)
    "idea_suggester":     ModelSpec("anthropic", "claude-sonnet-4-5", 2000),

    # Visual layer — one carousel OR image per LinkedIn post.
    "visual_format_decision": ModelSpec("anthropic", "claude-haiku-4-5", 340),
    "visual_carousel_copy":   ModelSpec("anthropic", "claude-sonnet-4-5", 2500),
    "visual_image_copy":      ModelSpec("anthropic", "claude-haiku-4-5", 600),
    # HiggsField hero/motion art-direction: one short abstract scene motif.
    "visual_hero_prompt":     ModelSpec("anthropic", "claude-haiku-4-5", 120),

    # VA prospecting tool — on-voice comments/DMs/email/SMS (3 variants/call).
    # Sonnet for voice fidelity; outputs are short so 700 tok is plenty.
    "prospect_draft":         ModelSpec("anthropic", "claude-sonnet-4-5", 700),

    # Lead-gen ICP tiebreak — only fires on borderline headlines (keyword score
    # decides the clear cases for free). Haiku, tiny JSON output.
    "lead_icp":               ModelSpec("anthropic", "claude-haiku-4-5", 300),

    # Lead-gen custom offer email — per enriched commenter, built from their
    # profile + comment + the post + the offer framework. Sonnet for quality.
    "offer_email":            ModelSpec("anthropic", "claude-sonnet-4-5", 900),

    # Lead-gen company enrichment (Phase 2) — summarize industry/size/what-they-do
    # from the company name + Firecrawl'd homepage text. Haiku, small JSON.
    "company_enrich":         ModelSpec("anthropic", "claude-haiku-4-5", 400),

    # Lead-gen qualification — decision-maker? provider vs prospect? small co? A cheap
    # Haiku pass on headline + comment, before any paid enrichment.
    "lead_qualify":           ModelSpec("anthropic", "claude-haiku-4-5", 300),

    # Cold-email 'Hermes' campaign-builder chat — conversational spec-gathering.
    "hermes_chat":            ModelSpec("anthropic", "claude-sonnet-4-5", 1500),
}


def for_task(task: str) -> ModelSpec:
    if task not in MODELS:
        raise KeyError(f"No model configured for task '{task}'. Add to MODELS.")
    return MODELS[task]


# ── Cost reference (updated when pricing changes) ────────────────────────────
# USD per million tokens; (input, output)

COST_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5":  (1.00,  5.00),
    "claude-opus-4-1":  (15.00, 75.00),
    "gpt-5":            (10.00, 30.00),  # placeholder
    "gpt-4o":            (2.50, 10.00),
    "gpt-4o-mini":       (0.15,  0.60),
}


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    in_p, out_p = COST_PER_MTOK.get(model_name, (3.0, 15.0))
    return (input_tokens / 1_000_000) * in_p + (output_tokens / 1_000_000) * out_p
