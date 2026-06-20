"""Thin wrapper around the HiggsField `hf` CLI (a self-contained Go binary).

Why the CLI and not the REST API: the binary owns auth, token refresh, media
upload, model params, and job polling. Re-implementing that against an
undocumented API would be fragile. The worker image bundles the linux binary
(Dockerfile.worker) and materializes a credentials file from env, so the same
`hf` commands you runs locally run on Railway.

Everything here is best-effort: every call returns None / [] on any failure so a
HiggsField hiccup never blocks a post. The visual layer always degrades:
video -> static hero card -> flat navy card -> text-only.

Token note: the binary refreshes the access token in place and writes it back to
the credentials file. In an ephemeral container that write is lost on restart,
where creds are re-materialized from env. If the refresh token has rotated since
the env var was set, you'll see "Session expired" — refresh HIGGSFIELD_TOKEN /
HIGGSFIELD_REFRESH_TOKEN on the worker. Failures are logged + degrade cleanly.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("visuals-higgs")

_BIN = os.getenv("HIGGSFIELD_BIN", "hf")
_DEFAULT_CREDS = str(Path.home() / ".config" / "higgsfield" / "credentials.json")

# Last CLI failure detail (stderr/reason), so callers can surface WHY a job
# didn't start into metadata for diagnosis without scraping container logs.
LAST_ERROR: str | None = None


def _creds_path() -> str:
    return os.getenv("HIGGSFIELD_CREDENTIALS_PATH") or _DEFAULT_CREDS


def is_enabled() -> bool:
    """True when we have a token (env or an existing creds file)."""
    if os.getenv("HIGGSFIELD_TOKEN") or os.getenv("HIGGSFIELD_API_KEY"):
        return True
    return Path(_creds_path()).is_file()


def _ensure_creds() -> bool:
    """Materialize the credentials file from env IFF it's absent.

    Only-if-absent so a token the binary has already refreshed in-place is never
    clobbered mid-run. Returns True when usable creds exist afterward.
    """
    path = Path(_creds_path())
    if path.is_file():
        return True
    token = os.getenv("HIGGSFIELD_TOKEN") or os.getenv("HIGGSFIELD_API_KEY")
    if not token:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"access_token": token}
        refresh = os.getenv("HIGGSFIELD_REFRESH_TOKEN")
        if refresh:
            payload["refresh_token"] = refresh
        path.write_text(json.dumps(payload))
        path.chmod(0o600)
        return True
    except Exception as e:  # noqa: BLE001
        _log.error("higgs_creds_write_failed", str(e))
        return False


def _env() -> dict:
    e = dict(os.environ)
    e["HIGGSFIELD_CREDENTIALS_PATH"] = _creds_path()
    e["HIGGSFIELD_NO_UPDATE_CHECK"] = "1"
    e.setdefault("NO_COLOR", "1")
    return e


def _run(args: list[str], timeout: int) -> dict | list | None:
    """Run `hf <args> --json` and parse stdout. None on any failure."""
    global LAST_ERROR
    if not _ensure_creds():
        LAST_ERROR = "unauthed (no creds)"
        _log.log("higgs_skipped_unauthed")
        return None
    cmd = [_BIN, *args, "--json", "--no-color"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, env=_env())
    except Exception as e:  # noqa: BLE001 (FileNotFound, timeout, ...)
        LAST_ERROR = f"exec_failed: {e}"
        _log.error("higgs_exec_failed", str(e), metadata={"cmd": args[:3]})
        return None
    if proc.returncode != 0:
        LAST_ERROR = (proc.stderr or proc.stdout or "")[:300].strip()
        _log.error("higgs_nonzero", LAST_ERROR,
                   metadata={"cmd": args[:3], "rc": proc.returncode})
        return None
    try:
        out = json.loads(proc.stdout.strip())
        LAST_ERROR = None
        return out
    except Exception as e:  # noqa: BLE001
        LAST_ERROR = f"bad_json: {proc.stdout[:160]}"
        _log.error("higgs_bad_json", str(e), metadata={"out": proc.stdout[:200]})
        return None


def _flag_args(params: dict | None) -> list[str]:
    out: list[str] = []
    for k, v in (params or {}).items():
        if v is None:
            continue
        out += [f"--{k}", str(v)]
    return out


def generate_sync(model: str, prompt: str, *, image: str | None = None,
                  params: dict | None = None, wait_timeout: str = "4m",
                  timeout: int = 300) -> list[str]:
    """Create a job and block until done. Returns result URLs ([] on failure).

    Use for images (seconds). Do NOT use for video — see create_async/poll.
    """
    args = ["generate", "create", model, "--prompt", prompt]
    if image:
        args += ["--image", image]
    args += _flag_args(params)
    args += ["--wait", "--wait-timeout", wait_timeout]
    data = _run(args, timeout=timeout)
    return _result_urls(data)


def create_async(model: str, prompt: str, *, image: str | None = None,
                 params: dict | None = None, timeout: int = 120) -> str | None:
    """Kick off a job WITHOUT waiting. Returns a job id to poll later (or None).

    For video: generation takes minutes, so we never block the cron on it. When
    an image is supplied, models disagree on the media flag, so we try `--image`
    then `--start-image` (the binary validates per-model) before giving up.
    """
    global LAST_ERROR
    media_flags = ["--image", "--start-image"] if image else [None]
    for mf in media_flags:
        args = ["generate", "create", model, "--prompt", prompt]
        if mf:
            args += [mf, image]
        args += _flag_args(params)
        data = _run(args, timeout=timeout)
        jid = _extract_job_id(data)
        if jid:
            return jid
        # _run succeeded but no id found → capture the shape so we can see it.
        if data is not None and not LAST_ERROR:
            LAST_ERROR = f"no job id in response: {json.dumps(data)[:240]}"
        # unrelated failure → stop retrying media-flag variants
        if mf and LAST_ERROR and "image" not in (LAST_ERROR or "").lower() \
                and "no job id" not in LAST_ERROR:
            break
    return None


def _extract_job_id(data) -> str | None:
    """Pull a job id from the (variable) create response shape."""
    if not data:
        return None
    candidates = data if isinstance(data, list) else [data]
    for c in candidates:
        # no-wait create returns a list of bare id strings: ["<uuid>"]
        if isinstance(c, str) and c.strip():
            return c.strip()
        if not isinstance(c, dict):
            continue
        for k in ("id", "job_id", "job_set_id", "jobSetId"):
            if c.get(k):
                return c[k]
        # nested: {"jobs":[{id}]} / {"job_set":{id}} / {"data":{...}}
        for nest in ("jobs", "job_set", "data", "result"):
            v = c.get(nest)
            if isinstance(v, list) and v and isinstance(v[0], dict) and v[0].get("id"):
                return v[0]["id"]
            if isinstance(v, dict):
                got = _extract_job_id(v)
                if got:
                    return got
    return None


def poll(job_id: str, timeout: int = 60) -> tuple[str, list[str]]:
    """Return (status, result_urls). status in completed|failed|in_progress|unknown."""
    data = _run(["generate", "get", job_id], timeout=timeout)
    jobs = data if isinstance(data, list) else ([data] if data else [])
    if not jobs:
        return "unknown", []
    statuses = [str((j or {}).get("status") or "").lower() for j in jobs]
    urls = _result_urls(jobs)
    if any(s in ("failed", "error", "canceled") for s in statuses):
        return "failed", urls
    if all(s in ("completed", "succeeded") for s in statuses) and statuses:
        return "completed", urls
    return "in_progress", urls


def _result_urls(data) -> list[str]:
    jobs = data if isinstance(data, list) else ([data] if data else [])
    urls: list[str] = []
    for j in jobs:
        if isinstance(j, dict) and j.get("result_url"):
            urls.append(j["result_url"])
    return urls


def download(url: str, timeout: int = 60) -> bytes | None:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.content
    except Exception as e:  # noqa: BLE001
        _log.error("higgs_download_failed", str(e), metadata={"url": url[:80]})
        return None
