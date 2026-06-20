-- Influencer system: who to engage with, tag, repost, repurpose.

create table if not exists influencers (
    id              uuid primary key default gen_random_uuid(),
    platform        text not null check (platform in ('linkedin','twitter','facebook')),
    handle          text not null,           -- @username or vanity slug
    profile_url     text not null,
    full_name       text,
    headline        text,                    -- LinkedIn headline / X bio
    bio             text,
    follower_count  int,
    pillars         text[] default '{}',     -- ['1','2'] which pillars they overlap
    relevance_score int default 50,          -- 0-100 LLM-assigned at discovery
    status          text default 'tracked'
                    check (status in ('tracked','snoozed','dropped')),
    discovered_via  text,                    -- 'manual' | 'llm_seed' | 'comment_thread' | 'group_post'
    last_engaged_at timestamptz,             -- when WE last commented/tagged/reposted
    last_post_at    timestamptz,             -- their most recent activity we know about
    metadata        jsonb default '{}'::jsonb,
    created_at      timestamptz default now(),
    unique(platform, handle)
);

create index if not exists influencers_active_idx
    on influencers (status, relevance_score desc, last_engaged_at nulls first);

create table if not exists influencer_posts (
    id              uuid primary key default gen_random_uuid(),
    influencer_id   uuid not null references influencers(id) on delete cascade,
    platform        text not null,
    external_id     text not null,           -- platform-native post ID
    posted_at       timestamptz,
    body            text,
    media_urls      text[] default '{}',
    post_url        text,
    likes           int,
    comments        int,
    reposts         int,
    relevance_score int,                     -- 0-100 on-topic for our pillars
    suggested_action text
                    check (suggested_action in ('comment','repost_with_commentary','repurpose','tag','ignore')),
    suggested_comment text,                  -- pre-drafted comment in your voice
    our_engagement_status text default 'none'
                    check (our_engagement_status in ('none','commented','reposted','repurposed','tagged','dismissed')),
    raw             jsonb default '{}'::jsonb,
    created_at      timestamptz default now(),
    unique(platform, external_id)
);

create index if not exists influencer_posts_brief_idx
    on influencer_posts (our_engagement_status, relevance_score desc, posted_at desc);
