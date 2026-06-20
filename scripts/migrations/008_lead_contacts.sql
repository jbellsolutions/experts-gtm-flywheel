-- Lead-gen pipeline: influencer top posts -> commenters -> dedupe -> ICP -> enrich.
--
-- Reuses the existing `influencers` (006) table for the influencer DB and
-- `influencer_posts` (006) for the scraped top posts. This migration adds:
--   * lead_contacts  — one row per UNIQUE commenter (dedup on profile_url),
--                      ICP-scored, optionally enriched with email/phone.
--   * leadgen_jobs   — the on-demand crawl queue drained by the worker
--                      (mirrors the rerun_drain / use_now_drain pattern).

create table if not exists lead_contacts (
    id                  uuid primary key default gen_random_uuid(),
    profile_url         text not null,            -- dedupe key (commenter LinkedIn URL)
    full_name           text,
    headline            text,                     -- fetched lazily for ICP-survivors only
    about               text,
    source_influencer_id uuid references influencers(id) on delete set null,
    source_post_url     text,                     -- the post we found them commenting on
    comment_text        text,                     -- what they commented (cheap ICP signal)
    prefilter_pass      boolean,                  -- survived the free pre-filter?
    icp_fit             boolean,                  -- final ICP verdict (post headline fetch)
    icp_score           int,                      -- 0-100
    icp_reason          text,
    email               text,
    phone               text,
    enrichment_status   text default 'none'
                        check (enrichment_status in ('none','queued','enriched','failed')),
    enriched_at         timestamptz,
    raw                 jsonb default '{}'::jsonb,
    created_at          timestamptz default now(),
    updated_at          timestamptz default now(),
    unique(profile_url)
);

create index if not exists lead_contacts_icp_idx
    on lead_contacts (icp_fit, icp_score desc, created_at desc);
create index if not exists lead_contacts_enrich_idx
    on lead_contacts (enrichment_status, icp_fit);

create table if not exists leadgen_jobs (
    id              uuid primary key default gen_random_uuid(),
    influencer_ids  uuid[] not null default '{}',
    caps            jsonb default '{}'::jsonb,    -- {top_posts, min_comments, max_commenters, since_days, enrich}
    status          text default 'queued'
                    check (status in ('queued','running','done','failed')),
    estimate        jsonb default '{}'::jsonb,    -- up-front credit estimate, shown in dashboard
    stats           jsonb default '{}'::jsonb,    -- credits spent, leads found, dropped counts
    error           text,
    created_at      timestamptz default now(),
    started_at      timestamptz,
    finished_at     timestamptz
);

create index if not exists leadgen_jobs_queue_idx
    on leadgen_jobs (status, created_at);
