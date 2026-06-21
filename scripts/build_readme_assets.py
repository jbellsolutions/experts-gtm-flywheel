#!/usr/bin/env python3
"""Render the README storefront graphics (premium dark, brand gradient) to docs/assets/*.png.

Each graphic is HTML/CSS with real Inter (embedded as base64), rendered headlessly via
Playwright -> system Chrome at 2x device scale for retina-crisp PNGs. These are PRODUCT
storefront assets (branded to the product we sell) using generic copy + obviously-fake
sample data only — no real brand names, leads, companies, or emails.

Regenerate all:        python scripts/build_readme_assets.py
Regenerate a subset:   python scripts/build_readme_assets.py hero flywheel
"""
from __future__ import annotations

import base64
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "brand" / "fonts"
OUT = ROOT / "docs" / "assets"
SCALE = 2  # device scale factor -> 2x PNGs


# ── shared brand chrome ──────────────────────────────────────────────────────
def _font_faces() -> str:
    weights = {400: "Inter-Regular.ttf", 600: "Inter-SemiBold.ttf",
               700: "Inter-Bold.ttf", 900: "Inter-Black.ttf"}
    css = []
    for w, f in weights.items():
        b64 = base64.b64encode((FONT_DIR / f).read_bytes()).decode("ascii")
        css.append("@font-face{font-family:'Inter';font-weight:%d;font-style:normal;"
                   "src:url(data:font/ttf;base64,%s) format('truetype')}" % (w, b64))
    return "".join(css)


BRAND_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{--navy:#0B1020;--glow:#7C3AED;--g0:#0EA5E9;--g1:#3457E0;--g2:#8B5CF6;
 --white:#fff;--light:#E7EAF2;--muted:#9AA6C0;--faint:#7E879B;--border:#28365A;
 --card:#121A30;--grad:linear-gradient(100deg,var(--g0),var(--g1) 52%,var(--g2))}
body{font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased;background:#05070f}
.frame{position:relative;overflow:hidden;color:var(--light);background:
 radial-gradient(72% 78% at 50% -14%, #7C3AED38, transparent 56%),
 radial-gradient(50% 60% at 104% -8%, #0EA5E926, transparent 52%),
 var(--navy)}
.frame::before{content:"";position:absolute;top:0;left:0;right:0;height:6px;background:var(--grad);z-index:5}
.gt{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.eyebrow{font-size:14px;font-weight:700;letter-spacing:3.5px;text-transform:uppercase}
.wm{display:flex;align-items:center;gap:11px;font-weight:700;letter-spacing:.5px;color:var(--light);font-size:16px}
.wm .dot{width:20px;height:20px;border-radius:50%;background:var(--grad);box-shadow:0 0 16px #8B5CF6aa}
"""


def page(body: str, css: str = "") -> str:
    return ("<!doctype html><html><head><meta charset=utf-8><style>"
            + _font_faces() + BRAND_CSS + css + "</style></head><body>" + body + "</body></html>")


def _check(size: int = 20) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none">'
            f'<path d="M5 12.6l4.3 4.3L19 7.2" stroke="#fff" stroke-width="2.7" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _flywheel_mark(size: int = 300) -> str:
    """Decorative flywheel ring (no labels) for the hero right side."""
    c = size / 2
    R = size * 0.40
    nodes = ""
    for ang in (-90, 0, 90, 180):
        x = c + R * math.cos(math.radians(ang))
        y = c + R * math.sin(math.radians(ang))
        nodes += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#0B1020" '
                  f'stroke="url(#hg)" stroke-width="3"/>'
                  f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="url(#hg)"/>')
    chev = ""
    for ang in (-45, 45, 135, 225):
        x = c + R * math.cos(math.radians(ang))
        y = c + R * math.sin(math.radians(ang))
        chev += (f'<g transform="translate({x:.1f},{y:.1f}) rotate({ang + 90})">'
                 f'<path d="M-5 -5 L5 0 L-5 5 Z" fill="url(#hg)" opacity="0.95"/></g>')
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" fill="none">'
        '<defs><linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#0EA5E9"/><stop offset="0.5" stop-color="#3457E0"/>'
        '<stop offset="1" stop-color="#8B5CF6"/></linearGradient>'
        '<radialGradient id="hglow" cx="0.5" cy="0.5" r="0.5">'
        '<stop offset="0" stop-color="#7C3AED" stop-opacity="0.55"/>'
        '<stop offset="1" stop-color="#7C3AED" stop-opacity="0"/></radialGradient></defs>'
        f'<circle cx="{c}" cy="{c}" r="{R*1.05:.0f}" fill="url(#hglow)"/>'
        f'<circle cx="{c}" cy="{c}" r="{R:.0f}" fill="none" stroke="url(#hg)" '
        f'stroke-width="3" stroke-opacity="0.55" stroke-dasharray="2 14" stroke-linecap="round"/>'
        f'<circle cx="{c}" cy="{c}" r="{R:.0f}" fill="none" stroke="url(#hg)" stroke-width="1.4" stroke-opacity="0.3"/>'
        f'{chev}{nodes}'
        f'<circle cx="{c}" cy="{c}" r="30" fill="#0B1020" stroke="url(#hg)" stroke-width="2" stroke-opacity="0.7"/>'
        f'<circle cx="{c}" cy="{c}" r="7" fill="url(#hg)"/>'
        '</svg>')


# ── 1. HERO ──────────────────────────────────────────────────────────────────
def hero():
    css = """
.hero{width:1200px;height:630px;display:flex;align-items:center;padding:0 84px}
.hero .l{flex:1;padding-right:24px}
.hero .eyebrow{color:transparent;background:var(--grad);-webkit-background-clip:text;background-clip:text;margin:22px 0 18px}
.hero h1{font-size:67px;line-height:1.0;font-weight:900;color:#fff;letter-spacing:-2px}
.hero .promise{font-size:30px;font-weight:800;color:#fff;margin-top:20px;letter-spacing:-.5px}
.hero .sub{font-size:18.5px;line-height:1.5;color:var(--muted);margin-top:15px;max-width:600px}
.hero .chip{display:inline-flex;align-items:center;gap:10px;margin-top:30px;padding:11px 18px;
 border:1px solid var(--border);border-radius:11px;background:#0c1326cc;font-size:15px;color:var(--light)}
.hero .chip .p{color:#5EE6C7;font-family:'Inter';font-weight:700}
.hero .chip b{color:#fff;font-weight:700}
.hero .r{width:330px;display:flex;align-items:center;justify-content:center}
.wm{position:absolute;top:40px;left:84px}
"""
    body = (
        '<div class="frame hero">'
        '<div class="wm"><span class="dot"></span>The Expert\'s GoToMarket Flywheel</div>'
        '<div class="l">'
        '<div class="eyebrow">Self-hosted content + lead engine</div>'
        '<h1>Own your audience.<br>Own your <span class="gt">pipeline.</span></h1>'
        '<div class="promise">Your content becomes a pipeline of real buyers.</div>'
        '<div class="sub">Turn what you know into demand across the three channels you '
        'actually own — LinkedIn, cold email, and your newsletter. No retainer. No '
        'middleman. No rented reach.</div>'
        '<div class="chip"><span class="p">&gt;_</span> drop in Claude Code &amp; say '
        '<b>&ldquo;set me up&rdquo;</b></div>'
        '</div>'
        f'<div class="r">{_flywheel_mark(320)}</div>'
        '</div>')
    return 1200, 630, page(body, css)


# ── 2. FLYWHEEL MECHANISM ────────────────────────────────────────────────────
def flywheel():
    W, H = 1200, 760
    cx, cy, R, nr = 600, 310, 150, 64
    defs = ('<defs><linearGradient id="fg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#0EA5E9"/><stop offset="0.5" stop-color="#3457E0"/>'
            '<stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs>')
    ring = (f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="url(#fg)" '
            f'stroke-width="2.5" stroke-opacity="0.45" stroke-dasharray="2 13" stroke-linecap="round"/>')
    # rotation chevrons (clockwise)
    chev = ""
    for ang in (-45, 45, 135, 225):
        x = cx + R * math.cos(math.radians(ang))
        y = cy + R * math.sin(math.radians(ang))
        chev += (f'<g transform="translate({x:.1f},{y:.1f}) rotate({ang + 90})">'
                 f'<path d="M-6 -6 L6 0 L-6 6 Z" fill="url(#fg)"/></g>')
    # 4 nodes: (angle, label, sublabel, sub-position)
    nodes_data = [
        (-90, "CONTENT", "your best thinking, posted", "top"),
        (0, "ATTENTION", "the right buyers engage", "right"),
        (90, "LEADS", "named, with verified emails", "bottom"),
        (180, "REVENUE", "conversations → clients", "left"),
    ]
    nodes = ""
    for ang, label, sub, pos in nodes_data:
        x = cx + R * math.cos(math.radians(ang))
        y = cy + R * math.sin(math.radians(ang))
        nodes += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{nr}" fill="#0E1528" '
                  f'stroke="url(#fg)" stroke-width="2.5"/>')
        nodes += (f'<text x="{x:.1f}" y="{y+6:.1f}" text-anchor="middle" font-family="Inter" '
                  f'font-size="18" font-weight="900" fill="#fff" letter-spacing="0.5">{label}</text>')
        if pos == "top":
            sx, sy, an = x, y - nr - 22, "middle"
        elif pos == "bottom":
            sx, sy, an = x, y + nr + 34, "middle"
        elif pos == "right":
            sx, sy, an = x + nr + 22, y + 5, "start"
        else:
            sx, sy, an = x - nr - 22, y + 5, "end"
        nodes += (f'<text x="{sx:.1f}" y="{sy:.1f}" text-anchor="{an}" font-family="Inter" '
                  f'font-size="16" font-weight="600" fill="#9AA6C0">{sub}</text>')
    center = (f'<circle cx="{cx}" cy="{cy}" r="58" fill="#0B1020" stroke="url(#fg)" '
              f'stroke-width="1.5" stroke-opacity="0.5"/>'
              f'<text x="{cx}" y="{cy-6}" text-anchor="middle" font-family="Inter" font-size="15" '
              f'font-weight="800" fill="#fff" letter-spacing="1">EACH TURN</text>'
              f'<text x="{cx}" y="{cy+16}" text-anchor="middle" font-family="Inter" font-size="15" '
              f'font-weight="800" fill="#fff" letter-spacing="1">COMPOUNDS</text>')
    svg = (f'<svg width="{W}" height="{H-120}" viewBox="0 0 {W} {H-120}" fill="none" '
           f'style="position:absolute;left:0;top:120px">{defs}{ring}{chev}{nodes}{center}</svg>')
    css = """
.fw{width:1200px;height:760px}
.fw .hd{position:absolute;top:60px;left:0;right:0;text-align:center}
.fw .eyebrow{color:transparent;background:var(--grad);-webkit-background-clip:text;background-clip:text}
.fw h2{font-size:40px;font-weight:900;color:#fff;letter-spacing:-1px;margin-top:12px}
.fw .hd p{font-size:17px;color:var(--muted);margin-top:10px}
"""
    body = (f'<div class="frame fw">'
            f'<div class="hd"><div class="eyebrow">The mechanism</div>'
            f'<h2>One flywheel. Every turn funds the next.</h2>'
            f'<p>Content earns attention &middot; attention becomes leads &middot; leads become revenue &middot; revenue makes more content.</p></div>'
            f'{svg}</div>')
    return W, H, page(body, css)


# ── 3. VALUE STACK ───────────────────────────────────────────────────────────
def value_stack():
    items = [
        ("Editorial content that sounds like you — and posts itself",
         "One recording becomes a week of LinkedIn posts plus your newsletter, in your voice, auto-published."),
        ("A LinkedIn engagement system that keeps you in front of buyers",
         "Every morning: the exact posts worth commenting on, each comment pre-drafted in your voice."),
        ("One-click lead capture, right in your browser",
         "See a post your buyers are all over? Click once and it drops into your funnel. Chrome + Edge."),
        ("A lead engine that turns attention into a named pipeline",
         "Everyone who engaged, pulled into your Airtable CRM with a verified work email."),
        ("Cold-email campaigns that build and send themselves",
         "Approve a lead and SmartLead sends, follows up, and stops the second they reply."),
        ("The whole flywheel — and you own every turn of it",
         "Self-hosted on your own accounts. About an hour a day. No platform can switch it off."),
    ]
    cards = ""
    for t, s in items:
        cards += (f'<div class="vc"><div class="ic">{_check(22)}</div>'
                  f'<div><div class="t">{t}</div><div class="s">{s}</div></div></div>')
    css = """
.vs{width:1200px;height:792px;padding:66px 74px}
.vs .eyebrow{color:transparent;background:var(--grad);-webkit-background-clip:text;background-clip:text}
.vs h2{font-size:42px;font-weight:900;color:#fff;letter-spacing:-1.2px;margin-top:12px}
.vs .grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:38px}
.vc{display:flex;gap:17px;background:linear-gradient(180deg,#131c33,#0f1729);
 border:1px solid var(--border);border-radius:18px;padding:24px 26px}
.vc .ic{flex:none;width:44px;height:44px;border-radius:12px;background:var(--grad);
 display:flex;align-items:center;justify-content:center;box-shadow:0 8px 20px #8B5CF63a}
.vc .t{font-size:19.5px;font-weight:800;color:#fff;line-height:1.25;letter-spacing:-.3px}
.vc .s{font-size:14.5px;color:var(--muted);margin-top:7px;line-height:1.48}
"""
    body = (f'<div class="frame vs">'
            f'<div class="eyebrow">Everything you get</div>'
            f'<h2>An entire go-to-market team, in a system you own.</h2>'
            f'<div class="grid">{cards}</div></div>')
    return 1200, 792, page(body, css)


# ── 4. SET-ME-UP (guided onboarding) ─────────────────────────────────────────
def setup():
    css = """
.su{width:1200px;height:600px;padding:58px 80px}
.su .eyebrow{color:transparent;background:var(--grad);-webkit-background-clip:text;background-clip:text}
.su h2{font-size:39px;font-weight:900;color:#fff;letter-spacing:-1px;margin-top:12px}
.su .win{margin-top:30px;background:#0B1120;border:1px solid var(--border);border-radius:16px;overflow:hidden;box-shadow:0 30px 80px #00000066}
.su .bar{display:flex;align-items:center;gap:8px;padding:13px 18px;background:#0e1526;border-bottom:1px solid var(--border)}
.su .bar i{width:12px;height:12px;border-radius:50%;display:block}
.su .bar .t{margin-left:10px;font-size:13px;color:var(--faint);font-weight:600}
.su .body{padding:24px 30px}
.su .ln{font-size:18px}
.su .you{color:#5EE6C7;font-weight:700}
.su .cmd{color:#fff;font-weight:800}
.su .bub{margin:14px 0 18px;padding:15px 19px;background:#131c33;border:1px solid var(--border);border-radius:12px;border-top-left-radius:3px;color:var(--light);font-size:15.5px;line-height:1.5;max-width:780px}
.su .bub b{color:#fff}
.su .step{display:flex;align-items:center;gap:11px;margin-top:10px;font-size:15.5px;color:var(--light)}
.su .step .c{width:22px;height:22px;border-radius:50%;background:var(--grad);display:flex;align-items:center;justify-content:center;flex:none}
.su .step.todo{color:var(--muted)}
.su .step.todo .c{background:#16203a;border:1px solid var(--g0)}
"""
    dots = ('<i style="background:#ff5f57"></i><i style="background:#febc2e"></i>'
            '<i style="background:#28c840"></i>')
    step = lambda t: '<div class="step"><span class="c">' + _check(13) + '</span>' + t + '</div>'
    body = ('<div class="frame su">'
            '<div class="eyebrow">Guided setup</div>'
            '<h2>You don’t install it. It installs itself.</h2>'
            '<div class="win"><div class="bar">' + dots
            + '<span class="t">Claude Code — The Expert’s GoToMarket Flywheel</span></div>'
            '<div class="body">'
            '<div class="ln"><span class="you">you ▸</span> <span class="cmd">set me up</span></div>'
            '<div class="bub">Welcome — here’s what we’re building together: a content + lead '
            'engine that <b>you own</b>. First, tell me a bit about <b>you and your offer</b>, and '
            'I’ll take it from there.</div>'
            + step('Brand voice written in your words')
            + step('Accounts connected — Anthropic, Airtable, SmartLead')
            + step('Deployed to Railway')
            + '<div class="step todo"><span class="c"></span>Your first posts are queued for approval</div>'
            + '</div></div></div>')
    return 1200, 600, page(body, css)


# ── 5. DASHBOARD MOCKUP ──────────────────────────────────────────────────────
def mockup_dashboard():
    css = """
.md{width:1200px;height:740px;display:flex;align-items:center;justify-content:center;padding:46px}
.bw{width:1080px;border-radius:14px;overflow:hidden;border:1px solid #2a3550;box-shadow:0 40px 100px #00000088}
.bc{display:flex;align-items:center;gap:8px;padding:12px 16px;background:#11192c}
.bc i{width:11px;height:11px;border-radius:50%;display:block}
.url{margin-left:14px;background:#0b1120;border:1px solid #2a3550;border-radius:8px;padding:6px 13px;font-size:12.5px;color:#7f93b5;font-weight:600}
.app{display:flex;height:580px;background:#fafafa;color:#0a0a0a}
.side{width:194px;background:#fff;border-right:1px solid #ededed;padding:18px 14px}
.logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:14.5px;color:#111;margin-bottom:20px}
.logo .d{width:17px;height:17px;border-radius:50%;background:linear-gradient(100deg,#0EA5E9,#8B5CF6)}
.nav{display:block;padding:9px 11px;border-radius:8px;color:#555;font-weight:600;font-size:13.5px;margin-bottom:3px}
.nav.on{background:#eff3ff;color:#2563eb}
.main{flex:1;padding:22px 24px}
.h{font-size:18px;font-weight:800;color:#111}
.sub{font-size:12.5px;color:#888;margin:3px 0 17px}
.card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;box-shadow:0 1px 2px #0000000d;padding:16px 17px;margin-bottom:13px}
.bd{display:flex;gap:6px;margin-bottom:11px}
.b{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px}
.b.pf{background:#0f172a;color:#fff}.b.vo{background:#e0f2fe;color:#0369a1}.b.pi{background:#f3e8ff;color:#7e22ce}
.pt{font-size:13px;line-height:1.5;color:#333}
.ac{display:flex;gap:8px;margin-top:13px}
.btn{font-size:12.5px;font-weight:700;padding:7px 15px;border-radius:8px}
.btn.go{background:#2563eb;color:#fff}.btn.gh{background:#f0f0f0;color:#444}
"""
    def draft(badges, txt):
        bs = "".join('<span class="b ' + c + '">' + t + '</span>' for c, t in badges)
        return ('<div class="card"><div class="bd">' + bs + '</div><div class="pt">' + txt
                + '</div><div class="ac"><span class="btn go">Approve</span>'
                '<span class="btn gh">Edit</span><span class="btn gh">Schedule</span></div></div>')
    nav = "".join('<span class="nav ' + c + '">' + t + '</span>' for t, c in
                  [("◆  Approve queue", "on"), ("Leads", ""), ("Comments", ""),
                   ("Ideas", ""), ("Newsletter", "")])
    cards = (draft([("pf", "LinkedIn"), ("vo", "Your Voice"), ("pi", "Story")],
                   "Most teams treat onboarding like a checklist. The best treat it as the first "
                   "90 days of proof. Here’s the framework we use to turn week one into a referral…")
             + draft([("pf", "Newsletter"), ("vo", "Your Voice"), ("pi", "How-to")],
                     "The 3 metrics that actually predict retention — and the 7 vanity ones we "
                     "stopped tracking last quarter…"))
    body = ('<div class="frame md"><div class="bw">'
            '<div class="bc"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i>'
            '<i style="background:#28c840"></i><span class="url">app.yourbrand.com / approve</span></div>'
            '<div class="app"><div class="side"><div class="logo"><span class="d"></span>Flywheel</div>'
            + nav + '</div><div class="main"><div class="h">Approve queue</div>'
            '<div class="sub">3 drafts ready · written in your voice · auto-posts when you approve</div>'
            + cards + '</div></div></div></div>')
    return 1200, 740, page(body, css)


# ── 6. AIRTABLE CRM MOCKUP ───────────────────────────────────────────────────
def mockup_airtable():
    css = """
.at{width:1200px;height:600px;display:flex;align-items:center;justify-content:center;padding:44px}
.aw{width:1080px;border-radius:14px;overflow:hidden;border:1px solid #2a3550;box-shadow:0 40px 100px #00000088;background:#fff;color:#1d1f25}
.ac2{display:flex;align-items:center;gap:8px;padding:11px 16px;background:#11192c}
.ac2 i{width:11px;height:11px;border-radius:50%;display:block}
.au{margin-left:14px;background:#0b1120;border:1px solid #2a3550;border-radius:8px;padding:6px 13px;font-size:12.5px;color:#7f93b5;font-weight:600}
.tabs{display:flex;gap:3px;padding:10px 16px 0;background:#f6f6f8;border-bottom:1px solid #e6e6e8}
.tab{font-size:13px;font-weight:700;padding:9px 17px;border-radius:8px 8px 0 0;color:#666}
.tab.on{background:#fff;color:#7c3aed}
.row{display:grid;grid-template-columns:148px 150px 150px 188px 108px 108px 128px;align-items:center;font-size:13px}
.row.hd{background:#f6f6f8;border-bottom:1px solid #e6e6e8;color:#888;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.cl{padding:13px 14px;border-bottom:1px solid #eff0f2;border-right:1px solid #f4f4f6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nm{font-weight:700;color:#111}
.em{color:#0a7d3c;font-weight:600}
.pl{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;display:inline-block}
.pv{background:#dbeafe;color:#1e40af}.po{background:#dcfce7;color:#166534}
.s1{background:#fef9c3;color:#854d0e}.s2{background:#e0e7ff;color:#3730a3}.s3{background:#f1f5f9;color:#475569}
"""
    rows_data = [
        ("Jordan Avery", "Acme Robotics", "VP Engineering", "jordan@acme.co", "s1", "✉ email drafted"),
        ("Priya Nair", "Northwind Labs", "Head of RevOps", "priya@northwind.io", "s2", "● in campaign"),
        ("Marcus Webb", "Lumen Studios", "Founder", "marcus@lumen.studio", "s3", "✓ enriched"),
        ("Dana Kim", "Brightpath", "Director, Growth", "dana@brightpath.co", "s1", "✉ email drafted"),
        ("Sam Ortiz", "Vertex Supply", "COO", "sam@vertexsupply.com", "s2", "● in campaign"),
        ("Lena Hahn", "Cobalt Health", "VP Marketing", "lena@cobalt.health", "s3", "✓ enriched"),
    ]
    hd = ('<div class="row hd"><div class="cl">Name</div><div class="cl">Company</div>'
          '<div class="cl">Title</div><div class="cl">Verified email</div><div class="cl">Voice</div>'
          '<div class="cl">Offer</div><div class="cl">Status</div></div>')
    rows = ""
    for nm, co, ti, em, sc, st in rows_data:
        rows += ('<div class="row"><div class="cl nm">' + nm + '</div><div class="cl">' + co
                 + '</div><div class="cl">' + ti + '</div><div class="cl em">' + em
                 + '</div><div class="cl"><span class="pl pv">Your Voice</span></div>'
                 '<div class="cl"><span class="pl po">Your Offer</span></div>'
                 '<div class="cl"><span class="pl ' + sc + '">' + st + '</span></div></div>')
    body = ('<div class="frame at"><div class="aw">'
            '<div class="ac2"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i>'
            '<i style="background:#28c840"></i><span class="au">airtable.com / Leads CRM</span></div>'
            '<div class="tabs"><span class="tab on">Contacts</span><span class="tab">Companies</span></div>'
            + hd + rows + '</div></div>')
    return 1200, 600, page(body, css)


# ── 7. ARCHITECTURE ──────────────────────────────────────────────────────────
def architecture():
    css = """
.ar{width:1200px;height:660px;padding:58px 74px}
.ar .eyebrow{color:transparent;background:var(--grad);-webkit-background-clip:text;background-clip:text}
.ar h2{font-size:37px;font-weight:900;color:#fff;letter-spacing:-1px;margin-top:12px}
.ar .cols{display:flex;align-items:center;margin-top:48px}
.ar .col{flex:1}
.ar .lbl{font-size:12px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:var(--faint);text-align:center;margin-bottom:15px}
.ar .box{background:linear-gradient(180deg,#141d35,#0f1729);border:1px solid var(--border);border-radius:14px;padding:17px 14px;text-align:center;margin-bottom:12px}
.ar .box .n{font-size:16.5px;font-weight:800;color:#fff}
.ar .box .d{font-size:12px;color:var(--muted);margin-top:3px}
.ar .arrow{width:56px;display:flex;align-items:center;justify-content:center}
.ar .acct{display:grid;grid-template-columns:1fr 1fr;gap:11px}
.ar .acct .box{margin:0}
.ar .foot{margin-top:40px;text-align:center;font-size:13.5px;color:var(--faint)}
.ar .foot b{color:var(--muted)}
"""
    box = lambda n, d: '<div class="box"><div class="n">' + n + '</div><div class="d">' + d + '</div></div>'
    defs = ('<svg width="0" height="0" style="position:absolute"><defs>'
            '<linearGradient id="ag" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#0EA5E9"/><stop offset="1" stop-color="#8B5CF6"/>'
            '</linearGradient></defs></svg>')
    chev = ('<div class="arrow"><svg width="28" height="28" viewBox="0 0 24 24" fill="none">'
            '<path d="M8 4l8 8-8 8" stroke="url(#ag)" stroke-width="2.5" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg></div>')
    col1 = '<div class="col"><div class="lbl">You operate</div>' + box("Dashboard", "Next.js · approve + run") + '</div>'
    col2 = ('<div class="col"><div class="lbl">It runs for you</div>'
            + box("Worker", "Python · scheduled jobs") + box("Browser-runner", "publishes long-form") + '</div>')
    col3 = ('<div class="col"><div class="lbl">Your accounts</div><div class="acct">'
            + box("Anthropic", "writes in your voice") + box("Airtable", "your lead CRM")
            + box("SmartLead", "sends &amp; follows up") + box("Unipile", "posts to LinkedIn") + '</div></div>')
    body = ('<div class="frame ar">' + defs + '<div class="eyebrow">How it’s built</div>'
            '<h2>Three small services. Your accounts. You own all of it.</h2>'
            '<div class="cols">' + col1 + chev + col2 + chev + col3 + '</div>'
            '<div class="foot">Plumbing you never touch: <b>Supabase</b> (state) · '
            '<b>Redis</b> (queue) · hosted on <b>Railway</b></div></div>')
    return 1200, 660, page(body, css)


# ── registry + render ────────────────────────────────────────────────────────
BUILDERS = {"hero": hero, "flywheel": flywheel, "value-stack": value_stack,
            "setup": setup, "mockup-dashboard": mockup_dashboard,
            "mockup-airtable": mockup_airtable, "architecture": architecture}


def render(names):
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for name in names:
            w, h, html = BUILDERS[name]()
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=SCALE)
            pg.set_content(html, wait_until="networkidle")
            pg.evaluate("() => document.fonts.ready")
            pg.locator(".frame").screenshot(path=str(OUT / f"{name}.png"))
            pg.close()
            print(f"  rendered docs/assets/{name}.png  ({w}x{h} @{SCALE}x)")
        b.close()


if __name__ == "__main__":
    names = sys.argv[1:] or list(BUILDERS)
    bad = [n for n in names if n not in BUILDERS]
    if bad:
        sys.exit(f"unknown asset(s): {bad}; known: {list(BUILDERS)}")
    render(names)
