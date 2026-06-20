-- daily_checklists gained kpis + context jsonb columns after migration 002.
-- These were originally ALTERed in manually on the organic project; this
-- migration makes them reproducible for any fresh deploy (e.g. client forks).

alter table daily_checklists add column if not exists kpis    jsonb default '{}'::jsonb;
alter table daily_checklists add column if not exists context jsonb default '{}'::jsonb;

