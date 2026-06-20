"""Prospecting API — tiny HTTP surface for the VA outreach generator.

Runs as its own Railway service (Dockerfile.api → uvicorn). Reuses the Python
voice + Firecrawl + LLM stack so generation lives in ONE place; the dashboard
"Prospecting" tab calls it server-side, and a future browser extension can call
the same endpoint with a per-user token.

Auth: shared secret in the `X-API-Key` header (PROSPECT_API_KEY).
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.content_flywheel.prospecting import generate as gen

# Called two ways: the dashboard over Railway's private network (server-side),
# and the browser extension cross-origin from a LinkedIn tab. CORS is open
# because every call is gated by the X-API-Key header (an Origin can't forge it).
app = FastAPI(title="prospect-api")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_API_KEY = os.getenv("PROSPECT_API_KEY")


class DraftRequest(BaseModel):
    channel: str
    prospect_url: str | None = None
    prospect_text: str | None = None
    post_url: str | None = None
    post_text: str | None = None
    thread_text: str | None = None
    voice: str = "ai_guy"


@app.get("/health")
def health() -> dict:
    return {"ok": True, "channels": list(gen.CHANNELS.keys())}


@app.post("/draft")
def draft(req: DraftRequest, x_api_key: str | None = Header(default=None)) -> dict:
    if not _API_KEY or x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")

    # Prefer pasted text; fall back to Firecrawl scrape of the URL (best-effort).
    prospect = req.prospect_text or (gen.scrape(req.prospect_url) if req.prospect_url else None) or ""
    post = req.post_text or (gen.scrape(req.post_url) if req.post_url else None) or ""
    thread = req.thread_text or ""

    try:
        result = gen.generate(req.channel, voice=req.voice or "ai_guy",
                              prospect=prospect, post=post, thread=thread)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result["used_scrape"] = {
        "prospect": bool(req.prospect_url and not req.prospect_text and prospect),
        "post": bool(req.post_url and not req.post_text and post),
    }
    if not result.get("variants"):
        raise HTTPException(status_code=502, detail="generation returned no variants")
    return result


def _dual_stack_socket(port: int):
    """IPv6 socket that ALSO accepts IPv4 (V6ONLY=0). Railway private networking
    is IPv6 (*.railway.internal); the public HTTP proxy connects over IPv4 — a
    plain `--host ::` is IPv6-only on this image and 502s the public proxy. A
    dual-stack socket serves both."""
    import socket
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    except (AttributeError, OSError):
        pass
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("::", port))
    s.listen(128)
    return s


if __name__ == "__main__":
    import asyncio
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    server = uvicorn.Server(uvicorn.Config(app, log_level="info"))
    asyncio.run(server.serve(sockets=[_dual_stack_socket(port)]))
