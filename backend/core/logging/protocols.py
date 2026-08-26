"""SoAI - Logging protocols for banner and streaming handlers [backend/core/logging/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncGenerator, Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Protocol

from core.errors.trace_logging import SoAILogger

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict, JSONValue

    type ExcInfoType = bool | tuple[
        type[BaseException],
        BaseException,
        TracebackType | None,
    ] | BaseException | None
    type LogArg = JSONValue

__all__ = (
    "CompressionHandlerProtocol",
    "LogBannerSystemProtocol",
    "LoggerProtocol",
    "LoggingManagerProtocol",
    "LoggingManagerSetupView",
    "LoggingManagerView",
    "TraceContextProtocol",
)


class LogBannerSystemProtocol(Protocol):
    def emit(self, key: str, *, message: str | None = None, level: int | None = None) -> None: ...

    def has_banner(self, key: str) -> bool: ...

    def register(self, key: str, *, color: str, message: str, level: int = 20) -> None: ...

    def emit_custom(self, *, color: str, message: str, level: int = 20) -> None: ...


class LoggerProtocol(Protocol):

    def debug(
        self,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def error(
        self,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def info(
        self,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def warning(
        self,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def critical(
        self,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def exception(
        self,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def log(
        self,
        level: int,
        msg: JSONValue,
        *args: LogArg,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None: ...

    def isEnabledFor(self, level: int) -> bool: ...

    @property
    def name(self) -> str: ...


TraceLogger = SoAILogger


if TYPE_CHECKING:
    type StandardLogger = logging.Logger | TraceLogger
else:
    StandardLogger = logging.Logger


class TraceContextProtocol(Protocol):
    @property
    def trace_id(self) -> str | None: ...


class CompressionHandlerProtocol(Protocol):
    @property
    def compress(self) -> bool: ...

    @property
    def compression_suffix(self) -> str: ...

    def rotate(self, source: str, dest: str) -> None: ...


class LoggingManagerView(Protocol):
    @property
    def disabled(self) -> bool: ...

    @property
    def lock(self) -> threading.RLock: ...

    streaming_handlers: dict[str, logging.Handler]


class LoggingManagerSetupView(LoggingManagerView, Protocol):
    @property
    def config_logging_enabled(self) -> bool: ...

    is_configured: bool
    config: ConfigProtocol | None
    main_loop: asyncio.AbstractEventLoop | None
    streaming_handlers: dict[str, logging.Handler]
    managed_third_party_loggers: list[str]
    third_party_log_levels: dict[str, int]

    def set_config_logging_enabled(self, enabled: bool) -> None: ...

    def shutdown_streaming_handler(
        self,
        handler: logging.Handler,
        root_logger: logging.Logger,
    ) -> None: ...

    def detach_streaming_handler_from_plugin(self, plugin_name: str) -> None: ...

    def setup_third_party_logging(self, root_level: int) -> None: ...

    def get_full_log_path(
        self,
        config: ConfigProtocol,
        filename_key: str,
        default_filename: str,
    ) -> str: ...

    def ensure_log_directory(self, log_file: str) -> bool: ...

    def get_log_file_path(self, config: ConfigProtocol) -> str: ...

    def get_rotation_handler(
        self,
        log_file: str,
        config: ConfigProtocol,
        formatter: logging.Formatter,
        encoding: str,
    ) -> logging.FileHandler: ...


class LoggingManagerProtocol(Protocol):
    streaming_handlers: dict[str, logging.Handler]

    def get_banner_system(self, logger: LoggerProtocol, width: int) -> LogBannerSystemProtocol: ...

    def get_streaming_handler(self, name: str) -> logging.Handler | None: ...

    def attach_streaming_handler_to_plugin(
        self,
        plugin_name: str,
        config: ConfigProtocol,
    ) -> None: ...

    def detach_streaming_handler_from_plugin(self, plugin_name: str) -> None: ...

    def stream_log_batches(
        self,
        source: str,
        *,
        batch_size: int,
        timeout: float,
        shutdown_event: asyncio.Event,
        idle_ping_interval: float = 0.2,
        min_batch_interval: float = 0.0,
        history_limit: int | None = None,
    ) -> AsyncGenerator[JSONDict]: ...

    def get_recent_logs(self, source: str, limit: int = 200) -> list[JSONDict]: ...

    def list_log_sources(self) -> list[str]: ...

    def has_log_source(self, source: str) -> bool: ...
