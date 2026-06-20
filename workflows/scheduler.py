"""Cron scheduler — runs registered jobs in a thread pool.

Aggregates JOBS lists from each workflow module so any new pipeline can
register cron-triggered work without touching this file.

Why a thread pool: several jobs (repurposer, use_now_drain, the editorial
pipeline) make *synchronous* Anthropic SDK calls — dozens of them per run.
If those run as plain asyncio tasks on the scheduler's own event loop, each
blocking LLM call freezes the loop, so the `while True` tick can't advance
and short-interval crons (use_now_drain every 2 min) silently stop firing.

Dispatching each job to a ThreadPoolExecutor — where it gets its own event
loop via asyncio.run — keeps the scheduler loop responsive no matter how
long or how blocking a job is. The scheduler thread only does cron math and
sleeps; the work happens elsewhere.

Run: `python -m workflows.scheduler` (the worker service entrypoint).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timezone
from typing import Awaitable, Callable

from croniter import croniter

from shared.logging.logger import AgentLogger
from workflows import content_pipeline

_log = AgentLogger("scheduler")

# Each entry: (cron_expression, async callable taking no args)
JOBS: list[tuple[str, Callable[[], Awaitable[None]]]] = [
    *content_pipeline.JOBS,
]

# Bounded pool so a burst of overlapping jobs can't spawn unbounded threads.
# 6 is plenty: most jobs are I/O bound and only a couple run concurrently.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=6, thread_name_prefix="job"
)

# Don't let the same job pile up: if a prior run of a job is still executing
# (e.g. a slow editorial drain), skip re-dispatching it until it finishes.
_inflight: set[str] = set()
_inflight_lock = __import__("threading").Lock()


def _run_job_blocking(name: str) -> None:
    """Run one job to completion in its own thread + event loop."""
    fn = _JOB_BY_NAME[name]
    started = datetime.now(timezone.utc)
    try:
        asyncio.run(fn())
        _log.log("job_done", metadata={"job": name, "started": started.isoformat()})
    except Exception as e:
        _log.error("job_error", str(e), metadata={"job": name})
    finally:
        with _inflight_lock:
            _inflight.discard(name)


# name -> fn lookup (names can repeat across modules; last one wins, which is
# fine — JOBS entries with the same fn name are the same callable).
_JOB_BY_NAME: dict[str, Callable[[], Awaitable[None]]] = {
    fn.__name__: fn for _, fn in JOBS
}


async def main() -> None:
    """Tick every 30 s; dispatch any job whose cron matched in the last minute."""
    _log.log("scheduler_start", metadata={"jobs": sorted(_JOB_BY_NAME.keys())})
    last_check = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    while True:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        if now > last_check:
            for cron_expr, fn in JOBS:
                next_fire = croniter(cron_expr, last_check).get_next(datetime)
                if next_fire <= now:
                    name = fn.__name__
                    with _inflight_lock:
                        if name in _inflight:
                            _log.log("job_skipped_inflight", metadata={"job": name})
                            continue
                        _inflight.add(name)
                    _EXECUTOR.submit(_run_job_blocking, name)
            last_check = now
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
