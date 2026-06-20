-- Group arbitrage. your already in groups; system tracks them, scans
-- engagement, surfaces who to comment-on / tag / repost.

create table if not exists groups (
    id              uuid primary key default gen_random_uuid(),
    platform        text not null check (platform in ('linkedin', 'facebook')),
    external_id     text not null,           -- FB group id or LI group urn
    group_url       text not null,
    group_name      text,
    member_count    int,
    -- member: we're in. pending: applied. not_yet: candidate. left: opted out.
    our_membership_status text default 'member'
                    check (our_membership_status in ('member','pending','not_yet','left')),
    relevance_score int default 50,          -- 0-100 LLM-assigned
    engagement_score int,                    -- avg reactions/post over last 30d
    last_scanned_at timestamptz,
    metadata        jsonb default '{}'::jsonb,
    created_at      timestamptz default now(),
    unique(platform, external_id)
);

create index if not exists groups_active_idx
    on groups (our_membership_status, relevance_score desc);

create table if not exists group_posts (
    id              uuid primary key default gen_random_uuid(),
    group_id        uuid not null references groups(id) on delete cascade,
    platform        text not null,
    external_id     text not null,
    posted_at       timestamptz,
    author_handle   text,                    -- can be promoted to influencer
    author_name     text,
    body            text,
    media_urls      text[] default '{}',
    likes           int,
    comments        int,
    relevance_score int,                     -- 0-100, on-topic for our pillars
    suggested_action text                    -- 'comment' | 'tag' | 'repurpose' | 'ignore'
                    check (suggested_action in ('comment','tag','repurpose','ignore')),
    suggested_comment text,                  -- pre-drafted in your voice
    our_engagement_status text default 'none'
                    check (our_engagement_status in ('none','commented','tagged','reposted','repurposed','dismissed')),
    raw             jsonb default '{}'::jsonb,
    created_at      timestamptz default now(),
    unique(platform, external_id)
);

create index if not exists group_posts_brief_idx
    on group_posts (our_engagement_status, relevance_score desc, posted_at desc);
