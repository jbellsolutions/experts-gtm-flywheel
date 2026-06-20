-- Content flywheel schema. Run via `make db-migrate`.

create table if not exists transcripts (
    id              uuid primary key default gen_random_uuid(),
    youtube_video_id text unique not null,
    title           text,
    pillar          text check (pillar in ('1', '2', 'both')),
    raw_text        text not null,
    cleaned_text    text,
    duration_sec    int,
    recorded_at     timestamptz,
    ingested_at     timestamptz default now()
);

create table if not exists drafts (
    id              uuid primary key default gen_random_uuid(),
    transcript_id   uuid references transcripts(id) on delete cascade,
    platform        text not null,                              -- linkedin | twitter | substack | medium | facebook | newsletter | shorts
    format          text not null,                              -- post | thread | article | carousel | shorts_clip | newsletter_section
    pillar          text not null check (pillar in ('1', '2', 'both')),
    body            text not null,
    metadata        jsonb default '{}'::jsonb,                  -- e.g. {"thread_parts": [...], "carousel_slides": [...], "shorts_start": 412}
    scheduled_for   timestamptz,                                -- assigned by slot_mapper
    status          text not null default 'pending'             -- pending | approved | edited | rejected | published | failed
                    check (status in ('pending','approved','edited','rejected','published','failed')),
    edit_diff       text,                                       -- diff between draft and edited body, for voice auto-tuning
    published_at    timestamptz,
    publish_url     text,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index if not exists drafts_status_scheduled_idx on drafts (status, scheduled_for);
create index if not exists drafts_transcript_idx on drafts (transcript_id);

create table if not exists inbound_messages (
    id              uuid primary key default gen_random_uuid(),
    platform        text not null,                              -- linkedin | youtube | twitter | facebook
    external_id     text not null,                              -- platform-native message/comment id
    thread_key      text,                                       -- dedupe key across platforms (person+topic)
    person_name     text,
    person_handle   text,
    person_company  text,
    body            text not null,
    detected_problem text,                                      -- extracted by lead_scorer if Pillar 1 problem mention
    lead_score      int default 0,                              -- 0-100; >=70 = hot
    status          text not null default 'new'                 -- new | replied | snoozed | dismissed | converted
                    check (status in ('new','replied','snoozed','dismissed','converted')),
    suggested_reply text,
    received_at     timestamptz not null,
    created_at      timestamptz default now(),
    unique (platform, external_id)
);

create index if not exists inbound_status_score_idx on inbound_messages (status, lead_score desc);


