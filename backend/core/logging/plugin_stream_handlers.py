"""SoAI - Plugin in-memory streaming handler lifecycle [backend/core/logging/plugin_stream_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import threading

from core.config.protocols import ConfigProtocol
from core.logging.configuration_constants import (
    DEFAULT_LOG_DATE_FORMAT,
    DEFAULT_LOG_FORMAT,
)
from core.logging.formatter_support import ROOT_LOGGER_NAME, resolve_log_level
from core.logging.formatters import UnifiedFormatter
from core.logging.handlers.streaming import StreamingLogHandler

__all__ = (
    "attach_streaming_handler_to_plugin",
    "detach_streaming_handler_from_plugin",
)


def attach_streaming_handler_to_plugin(
    *,
    plugin_name: str,
    config: ConfigProtocol,
    disabled: bool,
    config_logging_enabled: bool,
    lock: threading.RLock,
    streaming_handlers: dict[str, logging.Handler],
    main_loop: asyncio.AbstractEventLoop | None,
) -> None:
    if disabled or not config_logging_enabled:
        return
    attached = False
    with lock:
        if plugin_name in streaming_handlers:
            return
        streaming_handler = StreamingLogHandler(
            maxlen=config.get_int("OBSERVABILITY.LOGGING.STREAMING_LOG_BUFFER_SIZE"),
            loop=main_loop,
        )
        streaming_handler.set_loop(main_loop)
        log_format = DEFAULT_LOG_FORMAT
        date_format = DEFAULT_LOG_DATE_FORMAT
        streaming_handler.setFormatter(UnifiedFormatter(log_format, date_format, use_colors=False))
        plugin_logger = logging.getLogger(f"SoAI.Plugin.{plugin_name}")
        plugin_logger.addHandler(streaming_handler)
        log_level_value = config.get_str("OBSERVABILITY.LOGGING.LOG_LEVEL")
        normalized_level = (
            log_level_value.strip()
            if isinstance(log_level_value, str) and log_level_value.strip()
            else "INFO"
        )
        plugin_logger.setLevel(resolve_log_level(normalized_level))
        plugin_logger.propagate = False
        streaming_handlers[plugin_name] = streaming_handler
        attached = True
    if attached:
        logging.getLogger(ROOT_LOGGER_NAME).debug(
            "Attached in-memory streaming log handler to plugin '%s'.",
            plugin_name,
        )


def detach_streaming_handler_from_plugin(
    *,
    plugin_name: str,
    disabled: bool,
    lock: threading.RLock,
    streaming_handlers: dict[str, logging.Handler],
) -> None:
    if disabled:
        return
    detached = False
    with lock:
        streaming_handler = streaming_handlers.pop(plugin_name, None)
        if streaming_handler:
            logging.getLogger(f"SoAI.Plugin.{plugin_name}").removeHandler(streaming_handler)
            detached = True
    if detached:
        logging.getLogger(ROOT_LOGGER_NAME).info(
            "Detached in-memory streaming log handler from plugin '%s'.",
            plugin_name,
        )
