from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any


class AgentLogger:
    """Structured JSON logger with cost tracking per agent action."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._level = os.getenv("LOG_LEVEL", "INFO")

    def log(
        self,
        action: str,
        result: str = "success",
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        cost_usd: float = 0.0,
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": self.agent_id,
            "action": action,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
            "result": result,
            "metadata": metadata or {},
        }
        print(json.dumps(entry))

    def error(self, action: str, error: str, metadata: dict | None = None) -> None:
        self.log(action, result="error", metadata={**(metadata or {}), "error": error})
