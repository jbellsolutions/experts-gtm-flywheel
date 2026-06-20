"""Lead-gen pipeline: influencer top posts -> commenters -> dedupe -> ICP -> enrich.

Primary collector is ScrapeCreators (you owns credits; 1 credit per request,
not per comment). Apify `harvestapi` is a fallback. Bright Data enriches the
ICP-fits with email/phone. See scripts/migrations/008_lead_contacts.sql.
"""
