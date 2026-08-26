"""SoAI - Task registry configuration resolution [backend/tasks/registry/config_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.config.numeric import coerce_int_or_none
from core.config.protocols import ConfigProtocol

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "TaskRegistryInitValues",
    "resolve_task_registry_init_values",
)


class TaskRegistryInitValues(TypedDict, total=False):
    max_concurrent_per_owner: int
    max_concurrent_by_owner_type: dict[str, int]
    default_ttl_ms: int
    cleanup_interval_ms: int
    memory_cache_max_size: int
    terminal_grace_ms: int
    stuck_task_timeout_ms: int


def resolve_task_registry_init_values(config: ConfigProtocol | None) -> TaskRegistryInitValues:
    if config is None:
        return {}
    if not isinstance(config, ConfigProtocol):
        return {}
    max_default = _get_positive_int(
        config,
        "SYSTEM.TASKS.MAX_CONCURRENT_PER_OWNER",
        100,
    )
    max_by_owner_type = {
        "http_request": _get_positive_int(
            config,
            "SYSTEM.TASKS.MAX_CONCURRENT_PER_HTTP_REQUEST",
            max_default,
        ),
        "system": _get_positive_int(config, "SYSTEM.TASKS.MAX_CONCURRENT_PER_SYSTEM", max_default),
        "conversation": _get_positive_int(
            config,
            "SYSTEM.TASKS.MAX_CONCURRENT_PER_CONVERSATION",
            max_default,
        ),
        "mcp_client": _get_positive_int(
            config,
            "TOOLS.MCP.TASKS.MAX_CONCURRENT_PER_CLIENT",
            max_default,
        ),
    }
    return {
        "max_concurrent_per_owner": max_default,
        "max_concurrent_by_owner_type": max_by_owner_type,
        "default_ttl_ms": _get_positive_duration_ms(
            config,
            "SYSTEM.TASKS.DEFAULT_TTL_SECONDS",
            3600,
            minimum_seconds=1,
        ),
        "cleanup_interval_ms": _get_positive_duration_ms(
            config,
            "SYSTEM.TASKS.CLEANUP_INTERVAL_SECONDS",
            300,
            minimum_seconds=1,
        ),
        "memory_cache_max_size": _get_positive_int(
            config,
            "SYSTEM.TASKS.MEMORY_CACHE_MAX_SIZE",
            10000,
            minimum=100,
        ),
        "terminal_grace_ms": _get_positive_duration_ms(
            config,
            "SYSTEM.TASKS.TERMINAL_CACHE_GRACE_SECONDS",
            60,
            minimum_seconds=0,
        ),
        "stuck_task_timeout_ms": _get_positive_duration_ms(
            config,
            "SYSTEM.TASKS.STUCK_TASK_TIMEOUT_SECONDS",
            3600,
            minimum_seconds=0,
        ),
    }


def _get_positive_int(
    config: ConfigProtocol,
    key: str,
    default: int,
    *,
    minimum: int = 1,
) -> int:
    raw: ConfigValue | None = config.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        return max(int(default), minimum)
    value = coerce_int_or_none(
        raw,
        minimum=minimum,
        invalid_message=f"{key} must be an integer >= {minimum}.",
    )
    if value is None:
        return max(int(default), minimum)
    return value


def _get_positive_duration_ms(
    config: ConfigProtocol,
    key: str,
    default_seconds: int,
    *,
    minimum_seconds: int = 0,
) -> int:
    seconds_value = _get_positive_int(
        config,
        key,
        default_seconds,
        minimum=minimum_seconds,
    )
    return seconds_value * 1000
