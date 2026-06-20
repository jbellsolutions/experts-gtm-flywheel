-- Daily checklist for your morning routine.
-- One row per day. Items live as JSONB so we can evolve the shape without migrations.

create table if not exists daily_checklists (
    date            date primary key,
    items           jsonb not null default '[]'::jsonb,    -- [{id, label, scope, completed, completed_at, system_field}]
    summary         text,                                  -- short text shown in the morning Slack DM
    generated_at    timestamptz default now(),
    updated_at      timestamptz default now()
);

create index if not exists daily_checklists_date_idx on daily_checklists(date desc);
