-- Engagement metrics, snapshotted weekly.
-- One row per (draft_id, snapshot_at) so we can plot growth over time.

create table if not exists post_metrics (
    id              uuid primary key default gen_random_uuid(),
    draft_id        uuid not null references drafts(id) on delete cascade,
    platform        text not null,
    publish_url     text,
    snapshot_at     timestamptz default now(),

    -- Normalized numbers (best-effort across platforms; null if unavailable)
    impressions     int,
    likes           int,
    comments        int,
    reposts         int,
    clicks          int,
    -- Aggregate engagement = likes + comments + reposts (filled by fetcher)
    engagement      int,

    -- Raw payload from the platform API for forensics
    raw             jsonb default '{}'::jsonb,

    created_at      timestamptz default now()
);

create index if not exists post_metrics_draft_idx
    on post_metrics (draft_id, snapshot_at desc);
create index if not exists post_metrics_platform_idx
    on post_metrics (platform, snapshot_at desc);

-- Convenience view: latest snapshot per draft
create or replace view post_metrics_latest as
select distinct on (draft_id) *
from post_metrics
order by draft_id, snapshot_at desc;
