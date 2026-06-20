"""Newsletter adapter — Kit (formerly ConvertKit) v4 API.

Builds a branded, email-client-safe HTML broadcast (table layout + fully inline
styles — Gmail/Outlook strip <style> blocks and most modern CSS) with the
rendered cover image at the top, then creates the broadcast.

SEND SAFETY: a broadcast goes to the *whole list*, which is irreversible and
outward-facing. So sending is gated behind NEWSLETTER_AUTOSEND:
  - unset / false  -> create the broadcast as a Kit DRAFT (published=false, not
    sent). The dashboard/Slack gets the Kit URL so you review the real render
    in his inbox and hits send himself. (Default — safe.)
  - true           -> create + send the broadcast immediately.

Auth: X-Kit-Api-Key header with the key from
https://app.kit.com/account_settings/developer
"""
from __future__ import annotations

import html as _html
import os
import re

import httpx

from shared.logging.logger import AgentLogger
from shared.notifications.slack import SlackNotifier

_log = AgentLogger("publisher.newsletter")

KIT_BASE = "https://api.kit.com/v4"

# ── Brand (matches the visuals palette: blue → violet, Inter) ──────────────
_GRAD_A, _GRAD_B = "#0EA5E9", "#8B5CF6"
_INK = "#0F172A"
_MUTED = "#64748B"
_ACCENT = "#3457E0"
_BG = "#F1F5F9"
_FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,Helvetica,"
         "Arial,sans-serif")
_BRAND_NAME = os.getenv("NEWSLETTER_BRAND_NAME", "[Your Brand]")
_CTA_TEXT = os.getenv("NEWSLETTER_CTA_TEXT", "Work with us")
_CTA_URL = os.getenv("NEWSLETTER_CTA_URL", "https://yourdomain.com")


def _api_key() -> str:
    return (os.getenv("CONVERTKIT_API_KEY") or os.getenv("CONVERTKIT_API_SECRET")
            or os.getenv("KIT_API_KEY") or "")


def _autosend() -> bool:
    return (os.getenv("NEWSLETTER_AUTOSEND") or "").strip().lower() in (
        "1", "true", "yes", "on")


# ── Minimal markdown → email-safe HTML (inline styles per element) ──────────
def _inline(text: str) -> str:
    """Escape, then re-apply inline bold/italic/links. Operates on plain text."""
    s = _html.escape(text)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
               rf'<a href="\2" style="color:{_ACCENT};text-decoration:underline;">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r'<strong style="font-weight:700;">\1</strong>', s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def _md_to_html(md: str) -> str:
    """Tiny markdown subset → inline-styled block HTML. Handles ## / ### headings,
    - / * bullet lists, --- rules, blank-line paragraphs, bold/italic/links."""
    blocks: list[str] = []
    lines = md.replace("\r\n", "\n").split("\n")
    i, n = 0, len(lines)
    p_style = (f"margin:0 0 18px;font-size:16px;line-height:1.65;color:{_INK};"
               f"font-family:{_FONT};")
    while i < n:
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if re.match(r"^---+$", ln.strip()):
            blocks.append(f'<hr style="border:0;border-top:1px solid #E2E8F0;margin:26px 0;">')
            i += 1
            continue
        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            size = "22px" if lvl == 2 else "18px"
            blocks.append(
                f'<h{lvl} style="margin:26px 0 12px;font-size:{size};line-height:1.3;'
                f'font-weight:800;color:{_INK};font-family:{_FONT};">{_inline(m.group(2))}</h{lvl}>')
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i].rstrip()))
                i += 1
            lis = "".join(
                f'<li style="margin:0 0 8px;font-size:16px;line-height:1.6;color:{_INK};">'
                f"{_inline(it)}</li>" for it in items)
            blocks.append(f'<ul style="margin:0 0 18px;padding-left:22px;font-family:{_FONT};">{lis}</ul>')
            continue
        # paragraph: gather until blank line
        para = [ln]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{2,3}\s|\s*[-*]\s|---+$)", lines[i]):
            para.append(lines[i].rstrip())
            i += 1
        blocks.append(f'<p style="{p_style}">{_inline(" ".join(para))}</p>')
    return "\n".join(blocks)


def _split_title(body: str) -> tuple[str, str]:
    body = (body or "").strip()
    first, rest = (body.split("\n", 1) if "\n" in body else (body[:80], ""))
    return first.lstrip("# ").strip(), rest.strip()


def _render_email(title: str, body_md: str, cover_url: str | None) -> str:
    """Table-based, fully-inline-styled HTML email. Renders in Gmail/Outlook/Apple."""
    body_html = _md_to_html(body_md)
    cover = ""
    if cover_url:
        cover = (
            f'<tr><td style="padding:0;">'
            f'<img src="{_html.escape(cover_url)}" width="600" alt="{_html.escape(title)}" '
            f'style="display:block;width:100%;max-width:600px;height:auto;border:0;'
            f'border-radius:0;outline:none;text-decoration:none;"></td></tr>')
    return f"""\
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting"></head>
<body style="margin:0;padding:0;background:{_BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};">
<tr><td align="center" style="padding:24px 12px;">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0"
         style="width:600px;max-width:600px;background:#FFFFFF;border-radius:14px;overflow:hidden;
                box-shadow:0 1px 3px rgba(15,23,42,0.08);">
    <tr><td style="background:linear-gradient(90deg,{_GRAD_A},{_GRAD_B});
                   background-color:{_ACCENT};padding:22px 28px;">
      <span style="font-family:{_FONT};font-size:18px;font-weight:800;color:#FFFFFF;
                   letter-spacing:0.2px;">{_html.escape(_BRAND_NAME)}</span>
    </td></tr>
    {cover}
    <tr><td style="padding:28px 28px 8px;">
      <h1 style="margin:0 0 6px;font-size:26px;line-height:1.25;font-weight:800;
                 color:{_INK};font-family:{_FONT};">{_html.escape(title)}</h1>
    </td></tr>
    <tr><td style="padding:8px 28px 8px;">
      {body_html}
    </td></tr>
    <tr><td style="padding:8px 28px 30px;">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="border-radius:10px;background:{_ACCENT};">
          <a href="{_html.escape(_CTA_URL)}"
             style="display:inline-block;padding:12px 22px;font-family:{_FONT};font-size:15px;
                    font-weight:700;color:#FFFFFF;text-decoration:none;">{_html.escape(_CTA_TEXT)} &rarr;</a>
        </td></tr></table>
    </td></tr>
    <tr><td style="padding:20px 28px;border-top:1px solid #E2E8F0;">
      <p style="margin:0;font-family:{_FONT};font-size:12px;line-height:1.6;color:{_MUTED};">
        {_html.escape(_BRAND_NAME)} &middot; You're getting this because you subscribed.
        <!-- Kit auto-appends the compliant unsubscribe link to every broadcast. -->
      </p>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


async def publish(draft: dict) -> dict:
    api_key = _api_key()
    if not api_key:
        raise NotImplementedError(
            "Set CONVERTKIT_API_KEY in env "
            "(get it from https://app.kit.com/account_settings/developer)")

    title, content = _split_title(draft["body"])
    cover_url = ((draft.get("metadata") or {}).get("visual") or {}).get("image_url")
    html_body = _render_email(title, content, cover_url)
    autosend = _autosend()

    payload = {
        "subject": title,
        "content": html_body,
        "description": f"content_flywheel {draft['id']}",
        "public": False,
        "send_at": None,            # publisher already times this to the window
        "published": autosend,      # false => Kit DRAFT (not sent) until you send
    }
    headers = {"X-Kit-Api-Key": api_key, "Accept": "application/json",
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{KIT_BASE}/broadcasts", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json().get("broadcast", {})

    bid = data.get("id")
    url = f"https://app.kit.com/broadcasts/{bid}" if bid else ""
    _log.log("newsletter_broadcast", metadata={
        "id": bid, "autosend": autosend, "cover": bool(cover_url)})

    if not autosend:
        # Safe mode: handed to Kit as a draft. Tell you to review + send.
        try:
            await SlackNotifier().send(
                "ops",
                f":envelope: Newsletter *draft* ready in Kit (not sent): "
                f"\"{title}\" — review the render + send it: {url}\n"
                f"_(set NEWSLETTER_AUTOSEND=true to auto-send future issues.)_",
                "newsletter", priority="normal")
        except Exception:
            pass
    return {"url": url, "id": bid}
