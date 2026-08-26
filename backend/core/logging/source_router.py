"""SoAI - Logging source routing between core handlers and plugin files [backend/core/logging/source_router.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable

from core.config.clamped_numeric import read_config_int_min_clamped
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.logging.handlers.streaming import StreamingLogHandler
from core.logging.plugin_log_files import (
    list_plugin_log_sources,
    resolve_plugin_log_file,
)
from core.logging.plugin_log_streaming import (
    get_recent_plugin_log_entries,
    stream_plugin_log_batches,
)
from core.logging.streaming_batches import stream_log_batches
from core.types.json import JSONDict
from core.validation.integers import is_strict_int

__all__ = (
    "get_recent_log_entries",
    "has_log_source",
    "list_log_sources",
    "stream_source_log_batches",
)


def _resolve_plugin_log(config: ConfigProtocol | None, source: str) -> str | None:
    if config is None:
        return None
    if source == "core":
        return None
    return resolve_plugin_log_file(config, source)


def _resolve_history_limit(config: ConfigProtocol | None, history_limit: int | None) -> int:
    if history_limit is not None:
        if not is_strict_int(history_limit) or history_limit <= 0:
            raise ValidationError("history_limit must be a positive integer.")
        return history_limit
    if config is None:
        return 200
    return read_config_int_min_clamped(
        config,
        "OBSERVABILITY.LOGGING.STREAMING_LOG_BUFFER_SIZE",
        0,
        minimum=1,
    )


def list_log_sources(
    *,
    config: ConfigProtocol | None,
    streaming_handlers: dict[str, logging.Handler],
) -> list[str]:
    handler_sources = set(streaming_handlers.keys())
    plugin_sources: set[str] = set()
    if config is not None:
        plugin_sources = set(list_plugin_log_sources(config))
        plugin_sources.discard("core")
    sources = handler_sources | plugin_sources
    sources_without_core = sorted([name for name in sources if name != "core"])
    return (["core"] if "core" in sources else []) + sources_without_core


def has_log_source(
    *,
    config: ConfigProtocol | None,
    source: str,
    get_streaming_handler: Callable[[str], StreamingLogHandler | None],
) -> bool:
    if get_streaming_handler(source) is not None:
        return True
    try:
        return _resolve_plugin_log(config, source) is not None
    except ValidationError:
        return False


def get_recent_log_entries(
    *,
    config: ConfigProtocol | None,
    source: str,
    limit: int,
    streaming_handler: StreamingLogHandler | None,
) -> list[JSONDict]:
    plugin_log_path = _resolve_plugin_log(config, source)
    if plugin_log_path is not None:
        return get_recent_plugin_log_entries(source, plugin_log_path, limit)
    if not streaming_handler:
        raise ValidationError(f"Log source '{source}' not found.")
    return streaming_handler.get_recent(limit)


async def stream_source_log_batches(
    *,
    config: ConfigProtocol | None,
    source: str,
    handler: StreamingLogHandler | None,
    batch_size: int,
    timeout: float,
    shutdown_event: asyncio.Event,
    idle_ping_interval: float,
    min_batch_interval: float,
    history_limit: int | None,
    get_current_handler: Callable[[str], StreamingLogHandler | None],
) -> AsyncGenerator[JSONDict]:
    plugin_log_path = _resolve_plugin_log(config, source)
    if plugin_log_path is not None:
        async for payload in stream_plugin_log_batches(
            source,
            plugin_log_path,
            limit=_resolve_history_limit(config, history_limit),
            batch_size=batch_size,
            shutdown_event=shutdown_event,
            idle_ping_interval=idle_ping_interval,
        ):
            yield payload
        return
    if not handler:
        raise ValidationError(f"Log source '{source}' not found.")
    async for payload in stream_log_batches(
        handler=handler,
        source=source,
        batch_size=batch_size,
        timeout=timeout,
        shutdown_event=shutdown_event,
        idle_ping_interval=idle_ping_interval,
        min_batch_interval=min_batch_interval,
        get_current_handler=get_current_handler,
    ):
        yield payload
