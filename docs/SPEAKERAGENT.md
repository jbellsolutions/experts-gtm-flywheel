# SpeakerAgent Integration

The flywheel includes an optional **SpeakerAgent.ai** lane for experts who also want a
podcast-outreach workflow. This is separate from the LinkedIn and cold-email engine, but
it fits the same operator model: review leads, generate a pitch, send from your own inbox,
and keep status in sync.

## What is connected

- The dashboard includes a `SpeakerAgent` tab.
- It reads live podcast leads from the SpeakerAgent API.
- It can trigger a refresh to enrich the host and draft the outreach email.
- It can sync status changes and saved flags back to SpeakerAgent.
- It does not send email for you. You still send from your own inbox.

## Public integration surface

- CLI + skill: [jbellsolutions/speakeragent-cli](https://github.com/jbellsolutions/speakeragent-cli)
- API shape: podcasts-first workflow using `/api/podcasts*`

The old conferences or generic leads endpoints are not part of the current public
integration path.

## Required settings

Add these to `.env.local` or save them through the dashboard:

```bash
SPEAKERAGENT_API_URL=https://your-speakeragent-api.example.com
SPEAKERAGENT_API_KEY=your-api-key
SPEAKERAGENT_SPEAKER_ID=your-speaker-id
```

The dashboard reads env vars first, then falls back to saved `app_settings`.

## Basic flow

1. Open the `SpeakerAgent` tab.
2. Connect `API URL`, `X-API-Key`, and `speaker_id`.
3. Review the returned podcast cards.
4. Click `Generate pitch` when you want host enrichment plus a drafted outreach email.
5. Send from your own Gmail or email tool.
6. Update status and saved state as the conversation moves.

## CLI quickstart

```bash
export SPEAKERAGENT_API_URL=https://your-speakeragent-api.example.com
export SPEAKERAGENT_API_KEY=<your-key>
export SPEAKERAGENT_SPEAKER_ID=<your-speaker-id>

python3 speakeragent.py podcasts
python3 speakeragent.py refresh <id>
python3 speakeragent.py email <id>
python3 speakeragent.py status <id> Contacted
python3 speakeragent.py saved <id> true
```

## API endpoints used by the dashboard

- `GET /api/podcasts?speaker_id=<id>` - list podcast leads
- `PUT /api/podcasts/{id}/status` - update pipeline state
- `PUT /api/podcasts/{id}/saved` - toggle saved flag
- `POST /api/podcasts/{id}/refresh` - enrich host data and draft the outreach email

## Boundaries

- The flywheel does not mirror SpeakerAgent records into its own database.
- Status changes are safe because they do not trigger an email send.
- Host contact enrichment and draft generation happen on the SpeakerAgent side.
- This is an optional acquisition lane, not a required part of the flywheel install.
