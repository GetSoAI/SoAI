"""SoAI - Size-based compressed rotating handler [backend/core/logging/handlers/compressed_rotating.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import override

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.formatter_support import (
    ROOT_LOGGER_NAME,
    normalize_compression_suffix,
)
from core.logging.handlers.log_compression import CompressionHelper

__all__ = ("CompressedRotatingHandler",)

OPERATION_LOG_MANAGER_DO_ROLLOVER = "log_manager.do_rollover"
OPERATION_LOG_MANAGER_EMIT_FORMAT = "log_manager.emit.format"
OPERATION_LOG_MANAGER_EMIT_GETSIZE = "log_manager.emit.getsize"
OPERATION_LOG_MANAGER_EMIT_GET_MESSAGE = "log_manager.emit.get_message"
OPERATION_LOG_MANAGER_PROBE_INITIAL_ROLLOVER = "log_manager.probe_initial_rollover"
OPERATION_LOG_MANAGER_PROBE_INITIAL_ROLLOVER_OPEN = "log_manager.probe_initial_rollover.open"


NON_CRITICAL_ROTATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    RuntimeError,
    TypeError,
    ValueError,
    LookupError,
    AttributeError,
)


class CompressedRotatingHandler(RotatingFileHandler):
    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        errors: str | None = None,
        compress: bool = True,
        compression_suffix: str = ".gz",
    ) -> None:
        self.compress, self.compression_suffix = (
            compress,
            normalize_compression_suffix(compression_suffix),
        )
        self._compression = CompressionHelper(self)
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay, errors)

    def _probe_initial_rollover(self) -> None:
        probe_path = f"{self.baseFilename}.probe"
        try:
            stream_handle = self.stream
        except AttributeError:
            stream_handle = None
        if stream_handle and (not stream_handle.closed):
            stream_handle.close()
        try:
            os.rename(self.baseFilename, probe_path)
            os.rename(probe_path, self.baseFilename)
        except OSError as exception:
            log_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                exception,
                message=f"Log rotation failed critically for {self.baseFilename}: {exception}",
                operation=OPERATION_LOG_MANAGER_PROBE_INITIAL_ROLLOVER,
                details={"file_path": self.baseFilename, "probe_path": probe_path},
                level="critical",
            )
            if os.path.exists(probe_path):
                try:
                    os.rename(probe_path, self.baseFilename)
                except OSError as recovery_error:
                    logging.getLogger(ROOT_LOGGER_NAME).error(
                        "Log rotation recovery failed for %s: %s. Probe file remains at: %s",
                        self.baseFilename,
                        recovery_error,
                        probe_path,
                    )
        finally:
            if not self.delay:
                try:
                    self.stream = self._open()
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logging.getLogger(ROOT_LOGGER_NAME),
                        exception,
                        message="Failed to re-open log stream after rollover probe (non-critical).",
                        operation=OPERATION_LOG_MANAGER_PROBE_INITIAL_ROLLOVER_OPEN,
                        details={"file_path": self.baseFilename},
                        level="debug",
                    )
                    raise

    @override
    def emit(self, record: logging.LogRecord) -> None:
        should_rollover, current_size = (False, 0)
        if self.maxBytes > 0:
            try:
                current_size = os.path.getsize(self.baseFilename)
            except OSError:
                current_size = 0
            try:
                formatted_message = self.format(record)
            except NON_CRITICAL_ROTATION_EXCEPTIONS as formatting_exception:
                coerced_error = coerce_to_soai_error(
                    formatting_exception,
                    operation="log_manager.emit.format",
                )
                log_handled_exception(
                    logging.getLogger(ROOT_LOGGER_NAME),
                    coerced_error,
                    message="Failed to format log record for rotation sizing (non-critical).",
                    operation=OPERATION_LOG_MANAGER_EMIT_FORMAT,
                    details={"file_path": self.baseFilename},
                    level="debug",
                )
                try:
                    formatted_message = record.getMessage()
                except NON_CRITICAL_ROTATION_EXCEPTIONS as message_exception:
                    coerced_error = coerce_to_soai_error(
                        message_exception,
                        operation="log_manager.emit.get_message",
                    )
                    log_handled_exception(
                        logging.getLogger(ROOT_LOGGER_NAME),
                        coerced_error,
                        message=(
                            "Failed to read log record message for rotation sizing fallback "
                            "(non-critical)."
                        ),
                        operation=OPERATION_LOG_MANAGER_EMIT_GET_MESSAGE,
                        details={"file_path": self.baseFilename},
                        level="debug",
                    )
                    formatted_message = ""
            if current_size and current_size + len(formatted_message) + 1 >= self.maxBytes:
                should_rollover = True
        if should_rollover:
            self.doRollover()
        RotatingFileHandler.emit(self, record)
        if should_rollover or self.maxBytes <= 0:
            return
        try:
            new_size = os.path.getsize(self.baseFilename)
        except OSError as os_error:
            coerced_error = coerce_to_soai_error(
                os_error,
                operation="log_manager.emit.getsize",
            )
            log_handled_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                coerced_error,
                message="Failed to stat log file after write (non-critical).",
                operation=OPERATION_LOG_MANAGER_EMIT_GETSIZE,
                details={"file_path": self.baseFilename},
                level="debug",
            )
            return
        if current_size == 0 and new_size > self.maxBytes:
            self._probe_initial_rollover()
            return
        if new_size >= self.maxBytes:
            self.doRollover()

    @override
    def doRollover(self) -> None:
        try:
            if self.stream:
                self.stream.close()
            if self.backupCount > 0:
                for index in range(self.backupCount - 1, 0, -1):
                    source_path = self.rotation_filename(f"{self.baseFilename}.{index}")
                    destination_path = self.rotation_filename(f"{self.baseFilename}.{index + 1}")
                    src = self._compression.resolve_source_path(source_path)
                    if not src:
                        continue
                    self._compression.remove_destination(destination_path)
                    if self.compress and (not src.endswith(self.compression_suffix)):
                        self._compression.compress_and_rotate(src, destination_path)
                    else:
                        self.rotate(
                            src,
                            (
                                self._compression.apply_suffix(destination_path)
                                if self.compress
                                else destination_path
                            ),
                        )
                destination_path = self.rotation_filename(f"{self.baseFilename}.1")
                self._compression.remove_destination(destination_path)
                self._compression.compress_and_rotate(self.baseFilename, destination_path)
            if not self.delay:
                self.stream = self._open()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                exception,
                message=f"Log rotation failed critically for {self.baseFilename}: {exception}",
                operation=OPERATION_LOG_MANAGER_DO_ROLLOVER,
                details={"file_path": self.baseFilename},
                level="critical",
            )
            raise
