"""SoAI - Logging system initialization with handlers and formatters [backend/core/logging/setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Iterable

from core.config.protocols import ConfigProtocol
from core.errors.trace_logging import ensure_trace_logging
from core.logging.bootstrap import transition_bootstrap_loggers_to_runtime_logging
from core.logging.configuration_constants import (
    DEFAULT_JSON_LOG_FILENAME,
    DEFAULT_LOG_DATE_FORMAT,
    DEFAULT_LOG_ENCODING,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_HANDLER_TYPES,
)
from core.logging.formatter_support import ROOT_LOGGER_NAME, resolve_log_level
from core.logging.formatters import UnifiedFormatter
from core.logging.handlers.hash_chain_json import HashChainedJSONHandler
from core.logging.handlers.plugin_fanout import PluginLogFanoutHandler
from core.logging.handlers.streaming import StreamingLogHandler
from core.logging.protocols import LoggingManagerSetupView
from core.meta.version import __version__

__all__ = ("setup_logging",)


def setup_logging(
    manager: LoggingManagerSetupView,
    *,
    config: ConfigProtocol,
    main_loop: asyncio.AbstractEventLoop | None,
    banner_lines: Iterable[str],
) -> logging.Logger | None:
    ensure_trace_logging()
    if manager.disabled:
        return None
    with manager.lock:
        manager.config, manager.main_loop, was_configured = (
            config,
            main_loop,
            manager.is_configured,
        )
        manager.set_config_logging_enabled(config.get_bool("OBSERVABILITY.LOGGING.ENABLED"))
        root_logger = logging.getLogger(ROOT_LOGGER_NAME)
        python_root_logger = logging.getLogger()
        previous_root_handlers = list(root_logger.handlers)
        previous_handlers = list(previous_root_handlers)
        for handler in python_root_logger.handlers:
            if handler not in previous_handlers:
                previous_handlers.append(handler)
        if not manager.config_logging_enabled:
            sentinel_level = logging.CRITICAL + 1
            root_logger.setLevel(sentinel_level)
            root_logger.propagate = False
            python_root_logger.setLevel(sentinel_level)
            null_handler = logging.NullHandler()
            root_logger.handlers = [null_handler]
            python_root_logger.handlers = [null_handler]
            manager.setup_third_party_logging(sentinel_level)
            for handler in previous_handlers:
                if isinstance(handler, StreamingLogHandler):
                    manager.shutdown_streaming_handler(handler, root_logger)
                else:
                    handler.close()
            for handler_name, handler in list(manager.streaming_handlers.items()):
                if handler_name != "core":
                    manager.detach_streaming_handler_from_plugin(handler_name)
                if handler not in previous_root_handlers:
                    manager.shutdown_streaming_handler(handler, root_logger)
            manager.streaming_handlers.clear()
            audit_logger = logging.getLogger("SoAI.Audit")
            previous_audit_handlers = list(audit_logger.handlers)
            audit_logger.propagate = False
            audit_logger.handlers = [logging.NullHandler()]
            for handler in previous_audit_handlers:
                handler.close()
            audit_logger.setLevel(sentinel_level)
            logging.captureWarnings(True)
            manager.is_configured = True
            return root_logger
        log_level = resolve_log_level(config.require_str("OBSERVABILITY.LOGGING.LOG_LEVEL"))
        log_format = DEFAULT_LOG_FORMAT
        date_format = DEFAULT_LOG_DATE_FORMAT
        root_logger.setLevel(log_level)
        root_logger.propagate = False
        python_root_logger.setLevel(max(log_level, logging.WARNING))
        new_handlers: list[logging.Handler] = []
        handler_config = DEFAULT_LOG_HANDLER_TYPES
        encoding = DEFAULT_LOG_ENCODING
        log_file_path = manager.get_log_file_path(config)
        if "file" in handler_config and manager.ensure_log_directory(log_file_path):
            new_handlers.append(
                manager.get_rotation_handler(
                    log_file_path,
                    config,
                    UnifiedFormatter(log_format, date_format, use_colors=False),
                    encoding,
                ),
            )
            if config.get_bool("OBSERVABILITY.LOGGING.LOGGING_SYSTEM.MAIN_LOG_ENABLE_JSON_LOGGING"):
                json_file_path = manager.get_full_log_path(
                    config,
                    "",
                    DEFAULT_JSON_LOG_FILENAME,
                )
                if manager.ensure_log_directory(json_file_path):
                    new_handlers.append(
                        manager.get_rotation_handler(
                            json_file_path,
                            config,
                            UnifiedFormatter(None, use_colors=False, use_json=True),
                            encoding,
                        ),
                    )
        if "console" in handler_config and config.get_bool("OBSERVABILITY.LOGGING.CONSOLE_LOGGING"):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                UnifiedFormatter(
                    log_format,
                    date_format,
                    use_colors=config.get_bool("OBSERVABILITY.LOGGING.CONSOLE_COLOR"),
                ),
            )
            new_handlers.append(console_handler)
        streaming_handler_raw = manager.streaming_handlers.get("core")
        streaming_handler = (
            streaming_handler_raw
            if isinstance(streaming_handler_raw, StreamingLogHandler)
            else None
        )
        if "stream" in handler_config:
            buffer_size = config.get_int("OBSERVABILITY.LOGGING.STREAMING_LOG_BUFFER_SIZE")
            if not streaming_handler or streaming_handler.capacity != buffer_size:
                streaming_handler = StreamingLogHandler(maxlen=buffer_size)
                manager.streaming_handlers["core"] = streaming_handler
            streaming_handler.set_loop(manager.main_loop)
            new_handlers.append(streaming_handler)
        elif streaming_handler:
            manager.streaming_handlers.pop("core", None)
        streaming_formatter = UnifiedFormatter(log_format, date_format, use_colors=False)
        for handler in manager.streaming_handlers.values():
            if not isinstance(handler, StreamingLogHandler):
                continue
            handler.set_loop(manager.main_loop)
            handler.setLevel(log_level)
            handler.setFormatter(streaming_formatter)
        if "stream" in handler_config:
            new_handlers.append(PluginLogFanoutHandler(manager))
        for handler in new_handlers:
            handler.setLevel(log_level)
        root_logger.handlers = list(new_handlers)
        python_root_logger.handlers = list(new_handlers)
        manager.setup_third_party_logging(log_level)
        for handler in previous_handlers:
            if handler in new_handlers:
                continue
            if isinstance(handler, StreamingLogHandler):
                manager.shutdown_streaming_handler(handler, root_logger)
            else:
                handler.close()
        audit_logger = logging.getLogger("SoAI.Audit")
        previous_audit_handlers = list(audit_logger.handlers)
        audit_logger.propagate = False
        audit_logger.setLevel(logging.INFO)
        audit_logger.handlers = [
            HashChainedJSONHandler(
                manager.get_full_log_path(
                    config,
                    "OBSERVABILITY.LOGGING.AUDIT.PATH",
                    "soai.audit.jsonl",
                ),
                encoding,
            )
        ]
        for handler in previous_audit_handlers:
            handler.close()
        logging.captureWarnings(True)
        manager.is_configured = True
        transition_bootstrap_loggers_to_runtime_logging()
        log_message = (
            "Logging re-initialized - configuration has been hot-reloaded."
            if was_configured
            else "Logging initialized - logger configured successfully."
        )
    if not was_configured:
        root_logger.info("Welcome to SoAI v%s!", __version__)
        for line in banner_lines:
            root_logger.info(line)
    root_logger.info(log_message)
    return root_logger
