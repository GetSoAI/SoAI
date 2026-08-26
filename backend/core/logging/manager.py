"""SoAI - Central logging manager with streaming and rotation [backend/core/logging/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import threading
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.logging.banner import LogBannerSystem, get_colorized_ascii_banner_lines
from core.logging.formatter_support import ROOT_LOGGER_NAME
from core.logging.handlers.streaming import StreamingLogHandler
from core.logging.log_path_resolution import resolve_full_log_path
from core.logging.plugin_stream_handlers import (
    attach_streaming_handler_to_plugin,
    detach_streaming_handler_from_plugin,
)
from core.logging.protocols import LogBannerSystemProtocol, LoggerProtocol
from core.logging.rotation_handlers import create_rotation_handler
from core.logging.setup import setup_logging
from core.logging.source_router import (
    get_recent_log_entries,
    has_log_source,
    list_log_sources,
    stream_source_log_batches,
)
from core.logging.third_party_setup import setup_third_party_logging

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "LoggingManager",
    "LoggingManagerDependencies",
)

_UTILS_AVAILABLE = True


@dataclass(frozen=True, slots=True)
class LoggingManagerDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="LoggingManagerDependencies")


class LoggingManager:
    def __init__(self, deps: LoggingManagerDependencies) -> None:
        self._deps = deps
        self.lock = threading.RLock()
        self.is_configured = False
        self.disabled = not _UTILS_AVAILABLE
        self.config_logging_enabled = True
        self.streaming_handlers: dict[str, logging.Handler] = {}
        self._banner_systems: dict[str, LogBannerSystem] = {}
        self.config: ConfigProtocol | None = None
        self.main_loop: asyncio.AbstractEventLoop | None = None
        self.managed_third_party_loggers = [
            "uvicorn",
            "uvicorn.error",
            "pynvml",
            "filelock",
        ]
        self.third_party_log_levels = {
            "uvicorn": logging.INFO,
            "uvicorn.error": logging.INFO,
            "pynvml": logging.WARNING,
            "filelock": logging.WARNING,
        }

    def set_config_logging_enabled(self, enabled: bool) -> None:
        self.config_logging_enabled = bool(enabled)

    def _get_int_config(self, key: str, default: int) -> int:
        if self.config is None:
            return default
        try:
            return self.config.get_int(key)
        except (ValueError, TypeError) as exception:
            message = f"Invalid value for {key}."
            logging.getLogger(ROOT_LOGGER_NAME).error(message)
            raise ValidationError(message) from exception

    def ensure_log_directory(self, log_file: str) -> bool:
        directory_path = os.path.dirname(log_file)
        if directory_path and (not os.path.isdir(directory_path)):
            os.makedirs(directory_path, exist_ok=True)
        return True

    def get_full_log_path(
        self,
        config: ConfigProtocol,
        filename_key: str,
        default_filename: str,
    ) -> str:
        return resolve_full_log_path(
            config,
            filename_key=filename_key,
            default_filename=default_filename,
        )

    def get_log_file_path(self, config: ConfigProtocol) -> str:
        return (
            ""
            if self.disabled
            else self.get_full_log_path(config, "OBSERVABILITY.LOGGING.MAIN_LOG", "soai.log")
        )

    def get_streaming_handler(self, name: str) -> StreamingLogHandler | None:
        if self.disabled:
            return None
        if not self.config_logging_enabled:
            return None
        handler = self.streaming_handlers.get(name)
        return handler if isinstance(handler, StreamingLogHandler) else None

    def get_banner_system(self, logger: LoggerProtocol, width: int) -> LogBannerSystemProtocol:
        if self.disabled:
            raise StateError("Logging manager is disabled.")
        if not self.config_logging_enabled:
            raise StateError("Logging is disabled by configuration.")
        if width <= 0:
            raise ValidationError("Banner width must be a positive integer.")
        logger_key = logger.name or f"logger:{id(logger)}"
        with self.lock:
            banner_system = self._banner_systems.get(logger_key)
            if not banner_system or banner_system.width != width:
                banner_system = LogBannerSystem(logger, width)
                self._banner_systems[logger_key] = banner_system
        return banner_system

    def shutdown_streaming_handler(
        self,
        handler: logging.Handler,
        root_logger: logging.Logger,
    ) -> None:
        if handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        if isinstance(handler, StreamingLogHandler):
            handler.loop = None
            handler.clear_pending_messages()
        handler.close()

    async def stream_log_batches(
        self,
        source: str,
        *,
        batch_size: int,
        timeout: float,
        shutdown_event: asyncio.Event,
        idle_ping_interval: float = 0.2,
        min_batch_interval: float = 0.0,
        history_limit: int | None = None,
    ) -> AsyncGenerator[JSONDict]:
        if self.disabled:
            raise StateError("Logging manager is disabled.")
        if not self.config_logging_enabled:
            raise StateError("Logging is disabled by configuration.")
        if batch_size <= 0:
            raise ValidationError("batch_size must be a positive integer.")
        handler = self.get_streaming_handler(source)
        current_handler_getter = self.get_streaming_handler
        async for payload in stream_source_log_batches(
            config=self.config,
            handler=handler,
            batch_size=batch_size,
            timeout=timeout,
            source=source,
            shutdown_event=shutdown_event,
            idle_ping_interval=idle_ping_interval,
            min_batch_interval=min_batch_interval,
            history_limit=history_limit,
            get_current_handler=current_handler_getter,
        ):
            yield payload

    def attach_streaming_handler_to_plugin(self, plugin_name: str, config: ConfigProtocol) -> None:
        attach_streaming_handler_to_plugin(
            plugin_name=plugin_name,
            config=config,
            disabled=self.disabled,
            config_logging_enabled=self.config_logging_enabled,
            lock=self.lock,
            streaming_handlers=self.streaming_handlers,
            main_loop=self.main_loop,
        )

    def detach_streaming_handler_from_plugin(self, plugin_name: str) -> None:
        detach_streaming_handler_from_plugin(
            plugin_name=plugin_name,
            disabled=self.disabled,
            lock=self.lock,
            streaming_handlers=self.streaming_handlers,
        )

    def setup_logging(
        self,
        config: ConfigProtocol,
        main_loop: asyncio.AbstractEventLoop | None = None,
    ) -> logging.Logger | None:
        if self.disabled:
            return None
        return setup_logging(
            self,
            config=config,
            main_loop=main_loop,
            banner_lines=get_colorized_ascii_banner_lines(),
        )

    def get_recent_logs(self, source: str, limit: int = 200) -> list[JSONDict]:
        if self.disabled:
            return []
        if limit <= 0:
            raise ValidationError("limit must be a positive integer")
        with self.lock:
            handler = self.streaming_handlers.get(source)
            streaming_handler = handler if isinstance(handler, StreamingLogHandler) else None
        return get_recent_log_entries(
            config=self.config,
            source=source,
            limit=limit,
            streaming_handler=streaming_handler,
        )

    def list_log_sources(self) -> list[str]:
        if self.disabled or not self.config_logging_enabled:
            return []
        with self.lock:
            handlers = dict(self.streaming_handlers)
        return list_log_sources(config=self.config, streaming_handlers=handlers)

    def has_log_source(self, source: str) -> bool:
        return has_log_source(
            config=self.config,
            source=source,
            get_streaming_handler=self.get_streaming_handler,
        )

    def get_rotation_handler(
        self,
        log_file: str,
        config: ConfigProtocol,
        formatter: logging.Formatter,
        encoding: str,
    ) -> logging.FileHandler:
        return create_rotation_handler(
            log_file=log_file,
            config=config,
            formatter=formatter,
            encoding=encoding,
            get_int_config=self._get_int_config,
        )

    def setup_third_party_logging(self, root_level: int) -> None:
        root_logger = logging.getLogger(ROOT_LOGGER_NAME)
        setup_third_party_logging(
            root_logger=root_logger,
            managed_logger_names=self.managed_third_party_loggers,
            third_party_log_levels=self.third_party_log_levels,
            root_level=root_level,
        )
