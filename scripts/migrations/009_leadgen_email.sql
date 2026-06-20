-- Lead-gen: custom offer-email drafts per lead + editable app settings.
--
-- Extends 008 (lead_contacts + leadgen_jobs). Adds the auto-drafted offer email
-- columns on lead_contacts, and a tiny key/value settings table that holds the
-- editable "offer framework" the email generator follows (key = 'offer_framework').

alter table lead_contacts add column if not exists draft_subject text;
alter table lead_contacts add column if not exists draft_email   text;
alter table lead_contacts add column if not exists email_status  text default 'none'
    check (email_status in ('none','drafted','failed'));

create table if not exists app_settings (
    key         text primary key,
    value       text,
    updated_at  timestamptz default now()
);
