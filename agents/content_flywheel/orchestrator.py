"""Content flywheel orchestrator — boots all flywheel sub-agents."""
from __future__ import annotations

import asyncio
import importlib

from shared.logging.logger import AgentLogger

_log = AgentLogger("content-flywheel-orchestrator")

AGENTS = [
    "agents.content_flywheel.transcript_ingest.agent",
    "agents.content_flywheel.repurposer.agent",
    "agents.content_flywheel.publisher.agent",
    "agents.content_flywheel.inbound_monitor.agent",
    "agents.content_flywheel.review_queue.agent",
    "agents.content_flywheel.daily_checklist.agent",
]


async def main() -> None:
    _log.log("startup", metadata={"agents": AGENTS})
    tasks = []
    for module_path in AGENTS:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, "run"):
                tasks.append(asyncio.create_task(module.run()))
        except Exception as e:
            _log.error("agent_load", str(e), metadata={"module": module_path})

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
