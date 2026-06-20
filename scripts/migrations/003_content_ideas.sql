-- Content idea queue. you drops ideas; system suggests when queue runs low.

create table if not exists content_ideas (
    id              uuid primary key default gen_random_uuid(),

    -- Where the idea came from
    source          text not null
                    check (source in ('slack', 'auto_trend', 'auto_skool', 'auto_brand', 'manual')),

    -- The idea itself (raw text from you, or generated)
    content         text not null,

    -- If the idea included a URL we fetched, the parsed result lives here
    -- Shape: {kind: 'youtube'|'web'|'twitter', url, title, body, transcript, ...}
    parsed_content  jsonb default '{}'::jsonb,

    -- 0-100. you slack = 90, trends = 50, auto_brand = 30. Boostable.
    priority        int default 50,

    -- Lifecycle
    status          text not null default 'pending'
                    check (status in ('pending', 'used', 'dismissed')),
    used_in_transcript_id  uuid references transcripts(id),
    used_at         timestamptz,

    -- Free-form metadata (slack message ts, source url, fetch errors, etc)
    metadata        jsonb default '{}'::jsonb,

    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index if not exists content_ideas_active_idx
    on content_ideas (status, priority desc, created_at desc);

create index if not exists content_ideas_source_idx on content_ideas (source);

-- Track the last Slack message ts we processed, so the poller doesn't double-process
create table if not exists kv_state (
    key             text primary key,
    value           jsonb not null,
    updated_at      timestamptz default now()
);
