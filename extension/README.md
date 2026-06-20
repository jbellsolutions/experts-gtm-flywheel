# your brand Prospecting — Chrome extension

One-click on-voice outreach while prospecting on LinkedIn. Highlight a post (or
just open a profile), click the toolbar icon, pick a channel + voice, and get 3
drafts in your voice — tailored to the prospect and the post. Copy → paste →
send. Nothing is posted automatically.

## Install (sideload — not on the Chrome Web Store)

1. Copy the `extension/` folder somewhere permanent (e.g. `~/ai-guy-extension`).
2. Open `chrome://extensions` → toggle **Developer mode** (top right).
3. Click **Load unpacked** → select that folder.
4. Pin the extension. Click it → **Options** (or right-click → Options):
   - **Dashboard URL** — already pre-filled.
   - **Dashboard password** — the same password you use to open the dashboard.
   - Save.
5. Done. It's stored only in your browser. (No separate API key — it uses the dashboard login.)

## Use

1. On a LinkedIn post or profile, **highlight the relevant text** (the post body,
   or the prospect's headline). Optional but improves relevance.
2. Click the **your brand Prospecting** toolbar icon.
3. Pick a **channel** (comment / cold DM / connection note / DM reply / email / SMS)
   and a **voice** (your brand / Human-Loop / AI Reality).
4. The prospect + post boxes are pre-filled from the page — edit if needed.
5. **Generate 3 variants** → **Copy** the one you like → paste into LinkedIn.

## Notes

- Channels:
  - **Comment / "recent post"**: paste or highlight the post text.
  - **DM reply**: paste the conversation so far in the post/context box.
- It calls the same generation engine as the dashboard Prospecting tab (single
  source of truth for the voices).
