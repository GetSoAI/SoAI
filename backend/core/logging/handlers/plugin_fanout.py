"""SoAI - Plugin log fanout handler [backend/core/logging/handlers/plugin_fanout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import re
from typing import override

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.logging.formatter_support import ROOT_LOGGER_NAME
from core.logging.log_record import SoAILogRecord
from core.logging.protocols import LoggingManagerView

__all__ = ("PluginLogFanoutHandler",)

OPERATION_LOG_MANAGER_EMIT = "log_manager.emit"
OPERATION_LOG_MANAGER_EXTRACT_CANDIDATE_PLUGINS = "log_manager.extract_candidate_plugins"


NON_CRITICAL_FANOUT_EXCEPTIONS: tuple[type[Exception], ...] = (
    RuntimeError,
    TypeError,
    ValueError,
    LookupError,
    AttributeError,
    OSError,
)


class PluginLogFanoutHandler(logging.Handler):
    def __init__(self, manager: LoggingManagerView) -> None:
        super().__init__()
        self.manager = manager
        self._plugin_pattern = re.compile("plugin=['\\\"]([^'\\\"]+)['\\\"]", re.IGNORECASE)
        self._state_pattern = re.compile("State aggregated for '([^']+)'", re.IGNORECASE)

    def _extract_candidate_plugins(self, record: logging.LogRecord) -> set[str]:
        candidates: set[str] = set()
        record_plugin_name: str | None = None
        record_plugin: str | None = None
        record_plugin_id: str | None = None
        if isinstance(record, SoAILogRecord):
            record_plugin_name = record.plugin_name
            record_plugin = record.plugin
            record_plugin_id = record.plugin_id
        for candidate in (record_plugin_name, record_plugin, record_plugin_id):
            if isinstance(candidate, str):
                normalized = candidate.strip()
                if normalized:
                    candidates.add(normalized.lower())
        message = ""
        try:
            message = str(record.getMessage() or "")
        except NON_CRITICAL_FANOUT_EXCEPTIONS as exception:
            coerced_error = coerce_to_soai_error(
                exception,
                operation="log_manager.extract_candidate_plugins",
            )
            log_handled_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                coerced_error,
                message="Failed to read log record message for plugin fanout (non-critical).",
                operation=OPERATION_LOG_MANAGER_EXTRACT_CANDIDATE_PLUGINS,
                level="debug",
            )
            message = ""
        if message:
            for match in self._plugin_pattern.finditer(message):
                token = match.group(1).strip().lower()
                if token:
                    candidates.add(token)
            for match in self._state_pattern.finditer(message):
                token = match.group(1).strip().lower()
                if token:
                    candidates.add(token)
        return candidates

    @override
    def emit(self, record: logging.LogRecord) -> None:
        manager = self.manager
        if manager is None or manager.disabled:
            return
        candidates = self._extract_candidate_plugins(record)
        if not candidates:
            return
        try:
            with manager.lock:
                items = [
                    (name, handler)
                    for name, handler in manager.streaming_handlers.items()
                    if name != "core"
                ]
            if not items:
                return
            for name, handler in items:
                if name.lower() in candidates:
                    try:
                        handler.handle(record)
                    except NON_CRITICAL_FANOUT_EXCEPTIONS as exception:
                        coerced_error = coerce_to_soai_error(
                            exception,
                            operation="log_manager.emit",
                        )
                        log_exception(
                            logging.getLogger(ROOT_LOGGER_NAME),
                            coerced_error,
                            message=f"Failed to forward log record to plugin '{name}'",
                            operation=OPERATION_LOG_MANAGER_EMIT,
                            details={"plugin_name": name},
                            level="error",
                        )
        except NON_CRITICAL_FANOUT_EXCEPTIONS as exception:
            coerced_error = coerce_to_soai_error(
                exception,
                operation="log_manager.emit",
            )
            log_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                coerced_error,
                message="Error in PluginLogFanoutHandler",
                operation=OPERATION_LOG_MANAGER_EMIT,
                level="error",
            )
