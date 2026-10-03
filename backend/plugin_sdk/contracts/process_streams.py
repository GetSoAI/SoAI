"""SoAI - Process stream consumption helpers for plugins [backend/plugin_sdk/contracts/process_streams.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import logging
import re

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.formatter_support import resolve_log_level
from core.logging.plugin_log_entries import parse_plugin_log_line
from core.timing.constants import MODERATE_DELAY_SEC

__all__ = ("consume_process_stream",)

OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_CONSUME_PROCESS_STREAM = (
    "plugin_sdk.contracts.process_lifecycle.consume_process_stream"
)
OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_LOG_PROCESS_LOG_WRITE_FAILURE = (
    "plugin_sdk.contracts.process_lifecycle.log_process_log_write_failure"
)
PROCESS_STREAM_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


def _write_process_log_bytes(log_file_handle: io.BufferedIOBase, line_bytes: bytes) -> None:
    log_file_handle.write(line_bytes)
    log_file_handle.flush()


def _log_process_log_write_failure(
    *,
    logger: logging.Logger,
    plugin_label: str,
    exception: OSError | ValueError,
) -> None:
    coerced = coerce_to_soai_error(
        exception,
        operation=f"{plugin_label}.consume_stream.write",
    )
    log_exception(
        logger,
        coerced,
        message="Error writing process logs to file",
        operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_LOG_PROCESS_LOG_WRITE_FAILURE,
    )


async def _write_process_log_line(
    *,
    logger: logging.Logger,
    plugin_label: str,
    log_file_handle: io.BufferedIOBase,
    line_bytes: bytes,
) -> None:
    write_task = create_ephemeral_task(
        asyncio.to_thread(_write_process_log_bytes, log_file_handle, line_bytes),
        name=f"{plugin_label}-process-log-write",
        log_exceptions=False,
    )
    try:
        await asyncio.shield(write_task)
    except asyncio.CancelledError:
        await uncancel_and_wait(write_task)
        exception = write_task.exception() if not write_task.cancelled() else None
        if isinstance(exception, OSError | ValueError):
            _log_process_log_write_failure(
                logger=logger,
                plugin_label=plugin_label,
                exception=exception,
            )
        raise
    except (OSError, ValueError) as exception:
        _log_process_log_write_failure(
            logger=logger,
            plugin_label=plugin_label,
            exception=exception,
        )


async def consume_process_stream(
    stream: asyncio.StreamReader,
    *,
    logger: logging.Logger,
    log_file_handle: io.BufferedIOBase | None = None,
    plugin_label: str,
    strip_ansi: bool = False,
) -> None:
    while True:
        try:
            try:
                line_bytes = await asyncio.wait_for(
                    stream.readline(),
                    timeout=MODERATE_DELAY_SEC,
                )
            except TimeoutError:
                continue
            if not line_bytes:
                break

            line_text = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            level_name, _message = parse_plugin_log_line(line_text)
            level_number = resolve_log_level(level_name)
            record = logger.makeRecord(logger.name, level_number, __file__, 0, line_text, (), None)
            if not logger.filter(record):
                continue
            filtered_text = record.getMessage()
            filtered_bytes = (
                line_bytes
                if filtered_text == line_text and record.levelno == level_number
                else f"[{record.levelname}] {filtered_text}\n".encode("utf-8")
            )
            if log_file_handle is not None:
                await _write_process_log_line(
                    logger=logger,
                    plugin_label=plugin_label,
                    log_file_handle=log_file_handle,
                    line_bytes=filtered_bytes,
                )
            if strip_ansi:
                filtered_text = re.sub(
                    r"\x1b(?:[@-Z\-_]|\[[0-?][ -/][@-~])|\r",
                    "",
                    filtered_text,
                )
            if filtered_text and not logger.disabled and logger.isEnabledFor(record.levelno):
                record.msg = filtered_text
                record.args = ()
                logger.callHandlers(record)
        except asyncio.CancelledError:
            break
        except PROCESS_STREAM_OPERATION_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=f"{plugin_label}.consume_stream",
            )
            log_exception(
                logger,
                coerced,
                message="Error in process stream consumer",
                operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_CONSUME_PROCESS_STREAM,
            )
            break
