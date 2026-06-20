"""Your content flywheel — LinkedIn-first content engine.

Pipeline:
  YouTube live -> transcript_ingest -> repurposer -> review_queue
  Idea queue (Slack DMs + trends + LLM fallback) -> repurpose_from_ideas
                                                 -> use_now_drain (every 2 min)
  you approve in dashboard -> publisher -> LinkedIn / Substack / Medium / Newsletter

Publishing platforms: LinkedIn (Unipile), Substack (BU Cloud), Medium (BU Cloud),
Newsletter (Kit v4). Twitter / Facebook / YouTube Shorts and inbound-DM
monitoring are not part of this build.

Two pillars: "ask me anything" (Pillar 1) and "the certification journey" (Pillar 2).
"""
