"""SoAI - Real-time log streaming handler and queue [backend/core/logging/handlers/streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, override

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.formatter_support import ROOT_LOGGER_NAME
from core.logging.handlers.streaming_entries import (
    build_streaming_log_entry,
    clone_streaming_log_entry,
)
from core.logging.handlers.streaming_filter import StreamingFeedbackFilter

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("StreamingLogHandler",)

OPERATION_CORE_LOGGING_STREAMING_DISPATCH_MESSAGES = "core.logging.streaming.dispatch_messages"
OPERATION_CORE_LOGGING_STREAMING_EMIT_DISPATCH = "core.logging.streaming.emit.dispatch"
OPERATION_CORE_LOGGING_STREAMING_EMIT_FORMAT_RECORD = "core.logging.streaming.emit.format_record"
OPERATION_CORE_LOGGING_STREAMING_EMIT_QUEUE = "core.logging.streaming.emit.queue"


NON_CRITICAL_STREAMING_EXCEPTIONS: tuple[type[Exception], ...] = (
    RuntimeError,
    TypeError,
    ValueError,
    LookupError,
    AttributeError,
    OSError,
)

_STREAMING_HANDLER_SOURCE_FILE: str = __file__
_QUEUE_FULL_WARNING_INTERVAL_SECONDS: float = 30.0


class StreamingLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 200, loop: asyncio.AbstractEventLoop | None = None) -> None:
        super().__init__()
        self.queue: deque[JSONDict] = deque(maxlen=maxlen)
        self._lock = threading.RLock()
        self.listeners: set[asyncio.Queue[JSONDict]] = set()
        self.loop = loop
        self._pending_messages: deque[JSONDict] = deque(maxlen=maxlen)
        self._queue_full_last_warning_monotonic: float = 0.0
        self._queue_full_suppressed_warnings: int = 0
        self._total_dropped_messages: int = 0
        self.addFilter(StreamingFeedbackFilter(_STREAMING_HANDLER_SOURCE_FILE))

    @property
    def capacity(self) -> int:
        maxlen = self.queue.maxlen
        return maxlen if maxlen is not None else 0

    def clear_pending_messages(self) -> None:
        with self._lock:
            self._pending_messages.clear()

    def _deliver_batch_to_listener(
        self,
        queue: asyncio.Queue[JSONDict],
        messages: list[JSONDict],
    ) -> None:
        dropped_count = 0
        for message_entry in messages:
            try:
                queue.put_nowait(clone_streaming_log_entry(message_entry))
            except asyncio.QueueFull:
                dropped_count += 1
            except RuntimeError as exception:
                logging.getLogger(ROOT_LOGGER_NAME).debug(
                    "Failed to publish log message to listener: %s",
                    exception,
                )
                return
        if dropped_count > 0:
            self._total_dropped_messages += dropped_count
            now = time.monotonic()
            elapsed = now - self._queue_full_last_warning_monotonic
            if elapsed >= _QUEUE_FULL_WARNING_INTERVAL_SECONDS:
                suppressed = self._queue_full_suppressed_warnings
                self._queue_full_last_warning_monotonic = now
                self._queue_full_suppressed_warnings = 0
                if suppressed > 0:
                    logging.getLogger(ROOT_LOGGER_NAME).warning(
                        "Log listener queue full: %d message(s) dropped now, %d warning(s) suppressed since last report (total dropped: %d).",
                        dropped_count,
                        suppressed,
                        self._total_dropped_messages,
                    )
                else:
                    logging.getLogger(ROOT_LOGGER_NAME).warning(
                        "Log listener queue full: %d message(s) dropped (total dropped: %d).",
                        dropped_count,
                        self._total_dropped_messages,
                    )
            else:
                self._queue_full_suppressed_warnings += 1

    def add_listener(self, queue: asyncio.Queue[JSONDict]) -> None:
        with self._lock:
            self.listeners.add(queue)
            current_loop = self.loop
        if current_loop is None:
            try:
                self.set_loop(asyncio.get_running_loop())
            except RuntimeError as exception:
                logging.getLogger(ROOT_LOGGER_NAME).debug(
                    "Log listener loop unavailable: %s",
                    exception,
                )
        else:
            self._flush_pending_messages(current_loop)

    def remove_listener(self, queue: asyncio.Queue[JSONDict]) -> None:
        with self._lock:
            self.listeners.discard(queue)

    def set_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        if loop is None:
            return
        with self._lock:
            self.loop = loop
            loop_running = loop.is_running()
            pending_messages_list = (
                list(self._pending_messages) if loop_running and self._pending_messages else []
            )
            if loop_running:
                self._pending_messages.clear()
            listener_list = list(self.listeners) if loop_running and self.listeners else []
        if loop_running:
            self._dispatch_messages(loop, listener_list, pending_messages_list)

    def _flush_pending_messages(self, loop: asyncio.AbstractEventLoop | None) -> None:
        if loop is None or not loop.is_running():
            return
        with self._lock:
            if loop is not self.loop or not self._pending_messages or (not self.listeners):
                return
            listener_list, pending_messages_list = (
                list(self.listeners),
                list(self._pending_messages),
            )
            self._pending_messages.clear()
        self._dispatch_messages(loop, listener_list, pending_messages_list)

    def _dispatch_messages(
        self,
        loop: asyncio.AbstractEventLoop,
        listeners: list[asyncio.Queue[JSONDict]],
        messages: list[JSONDict],
    ) -> None:
        if not listeners or not messages:
            return
        if loop.is_closed():
            logging.getLogger(ROOT_LOGGER_NAME).debug(
                "Skipping log dispatch because target loop is closed.",
            )
            with self._lock:
                self._pending_messages.extend(messages)
            return
        for listener_queue in listeners:
            try:
                loop.call_soon_threadsafe(
                    self._deliver_batch_to_listener,
                    listener_queue,
                    messages,
                )
            except NON_CRITICAL_STREAMING_EXCEPTIONS as exception:
                coerced_error = coerce_to_soai_error(
                    exception,
                    operation="core.logging.streaming.dispatch_messages",
                )
                log_handled_exception(
                    logging.getLogger(ROOT_LOGGER_NAME),
                    coerced_error,
                    message="Failed to enqueue log batch for streaming (non-critical).",
                    operation=OPERATION_CORE_LOGGING_STREAMING_DISPATCH_MESSAGES,
                    level="debug",
                )

    def get_recent(self, limit: int) -> list[JSONDict]:
        if limit <= 0:
            return []
        with self._lock:
            entries = list(self.queue)
        return [
            clone_streaming_log_entry(item)
            for item in (entries[-limit:] if limit < len(entries) else entries)
        ]

    @override
    def emit(self, record: logging.LogRecord) -> None:
        record_name = record.name
        try:
            formatted_text = self.format(record)
        except NON_CRITICAL_STREAMING_EXCEPTIONS as exception:
            coerced_error = coerce_to_soai_error(
                exception,
                operation="core.logging.streaming.emit.format_record",
            )
            log_handled_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                coerced_error,
                message="Failed to format log record for streaming (non-critical).",
                operation=OPERATION_CORE_LOGGING_STREAMING_EMIT_FORMAT_RECORD,
                level="debug",
            )
            self.handleError(record)
            return
        entry = build_streaming_log_entry(
            record,
            formatted_text=formatted_text,
            logger_name=record_name,
            formatter=self.formatter,
        )
        listener_list: list[asyncio.Queue[JSONDict]] = []
        pending_messages_list: list[JSONDict] = []
        event_loop = None
        try:
            with self._lock:
                cloned_entry = clone_streaming_log_entry(entry)
                self.queue.append(cloned_entry)
                event_loop = self.loop
                if event_loop is None:
                    try:
                        event_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        event_loop = None
                    else:
                        self.loop = event_loop
                if event_loop is None or not event_loop.is_running():
                    self._pending_messages.append(cloned_entry)
                    return
                if self._pending_messages:
                    pending_messages_list.extend(self._pending_messages)
                    self._pending_messages.clear()
                pending_messages_list.append(cloned_entry)
                listener_list = list(self.listeners)
        except NON_CRITICAL_STREAMING_EXCEPTIONS as exception:
            coerced_error = coerce_to_soai_error(
                exception,
                operation="core.logging.streaming.emit.queue",
            )
            log_handled_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                coerced_error,
                message="Failed to append log record to streaming queue (non-critical).",
                operation=OPERATION_CORE_LOGGING_STREAMING_EMIT_QUEUE,
                level="debug",
            )
            self.handleError(record)
            return
        try:
            self._dispatch_messages(event_loop, listener_list, pending_messages_list)
        except NON_CRITICAL_STREAMING_EXCEPTIONS as exception:
            coerced_error = coerce_to_soai_error(
                exception,
                operation="core.logging.streaming.emit.dispatch",
            )
            log_handled_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                coerced_error,
                message="Failed to dispatch log records to listeners (non-critical).",
                operation=OPERATION_CORE_LOGGING_STREAMING_EMIT_DISPATCH,
                level="debug",
            )
            self.handleError(record)
