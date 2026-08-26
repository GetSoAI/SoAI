"""SoAI - Streaming first-chunk timeout resolution [backend/core/tasks/streaming_prefill_timeout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.config.numeric import coerce_positive_float
from core.tasks.prompt_token_metadata import resolve_task_prompt_tokens
from core.tasks.task import Task
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.types.json import JSONValue

__all__ = (
    "DEFAULT_STREAMING_PREFILL_MIN_TOKENS_PER_SEC",
    "DEFAULT_STREAMING_PREFILL_OVERHEAD_SEC",
    "resolve_streaming_first_chunk_timeout",
)

DEFAULT_STREAMING_PREFILL_MIN_TOKENS_PER_SEC: float = 50.0
DEFAULT_STREAMING_PREFILL_OVERHEAD_SEC: float = 60.0
STREAMING_TIMEOUT_MINIMUM: float = 1.0


def _resolve_explicit_request_timeout(task: Task) -> float | None:
    context = task.orchestration_context
    if context is None or context.event is None:
        return None
    timeout_value = context.event.payload.get("timeout")
    if isinstance(timeout_value, bool) or not isinstance(timeout_value, int | float):
        return None
    if float(timeout_value) <= 0:
        return None
    return float(timeout_value)


def _resolve_health_float(
    health_check_config: Mapping[str, JSONValue],
    key: str,
    default: float,
) -> float:
    return coerce_positive_float(
        health_check_config.get(key, default),
        default=default,
        minimum=STREAMING_TIMEOUT_MINIMUM,
    )


def resolve_streaming_first_chunk_timeout(
    *,
    task: Task,
    health_check_config: Mapping[str, JSONValue],
) -> float:
    base_timeout = _resolve_health_float(
        health_check_config,
        "NON_STREAMING_TIMEOUT_SEC",
        LONG_REQUEST_TIMEOUT_SEC,
    )
    prompt_tokens = resolve_task_prompt_tokens(task)
    resolved_timeout = base_timeout
    if prompt_tokens is not None and prompt_tokens > 0:
        prefill_tokens_per_second = _resolve_health_float(
            health_check_config,
            "STREAMING_PREFILL_MIN_TOKENS_PER_SEC",
            DEFAULT_STREAMING_PREFILL_MIN_TOKENS_PER_SEC,
        )
        prefill_overhead_seconds = _resolve_health_float(
            health_check_config,
            "STREAMING_PREFILL_OVERHEAD_SEC",
            DEFAULT_STREAMING_PREFILL_OVERHEAD_SEC,
        )
        prompt_prefill_timeout = (float(prompt_tokens) / prefill_tokens_per_second) + float(
            prefill_overhead_seconds,
        )
        resolved_timeout = max(base_timeout, prompt_prefill_timeout)
    explicit_timeout = _resolve_explicit_request_timeout(task)
    if explicit_timeout is None:
        return resolved_timeout
    return min(resolved_timeout, max(STREAMING_TIMEOUT_MINIMUM, explicit_timeout))
