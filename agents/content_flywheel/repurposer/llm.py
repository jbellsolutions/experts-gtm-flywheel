"""Provider-agnostic LLM wrapper.

Repurposer + inbound_monitor + browser_runner all call `complete(task, system, user)`
and the routing happens here based on `model_config.MODELS`.
"""
from __future__ import annotations

import os
from functools import lru_cache

from shared.auth.vault import get_secret
from shared.logging.logger import AgentLogger

from .model_config import ModelSpec, estimate_cost, for_task

_log = AgentLogger("llm")


@lru_cache(maxsize=1)
def _anthropic_client():
    from anthropic import Anthropic
    return Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "")


def complete(task: str, system: str, user: str, *, model_override: ModelSpec | None = None) -> str:
    spec = model_override or for_task(task)
    if spec.provider == "anthropic":
        return _anthropic(spec, system, user, task)
    if spec.provider == "openai":
        return _openai(spec, system, user, task)
    raise ValueError(f"Unknown provider {spec.provider!r} for task {task!r}")


def _anthropic(spec: ModelSpec, system: str, user: str, task: str) -> str:
    msg = _anthropic_client().messages.create(
        model=spec.name,
        max_tokens=spec.max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = msg.content[0].text.strip()
    cost = estimate_cost(spec.name, msg.usage.input_tokens, msg.usage.output_tokens)
    _log.log("complete", model=spec.name, input_tokens=msg.usage.input_tokens,
             output_tokens=msg.usage.output_tokens, cost_usd=cost,
             metadata={"task": task})
    return text


def _openai(spec: ModelSpec, system: str, user: str, task: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"task '{task}' is configured for OpenAI ({spec.name}) but "
            f"OPENAI_API_KEY is not set."
        )
    resp = _openai_client().chat.completions.create(
        model=spec.name,
        max_tokens=spec.max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    text = resp.choices[0].message.content.strip()
    usage = resp.usage
    cost = estimate_cost(spec.name, usage.prompt_tokens, usage.completion_tokens)
    _log.log("complete", model=spec.name, input_tokens=usage.prompt_tokens,
             output_tokens=usage.completion_tokens, cost_usd=cost,
             metadata={"task": task})
    return text
