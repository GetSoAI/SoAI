"""SoAI - Shared IPC stream writer close handling [backend/core/ipc/stream_closing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONDict, JSONValue

__all__ = ("close_ipc_writer", "is_ipc_peer_closed_exception")

LOGGER_NAME = "SoAI.core.ipc.stream_closing"
OPERATION_CLOSE_CONNECTION = "core.ipc.stream_closing.close_writer"
IPC_CLOSE_EXCEPTIONS: tuple[type[Exception], ...] = RECOVERABLE_EXCEPTIONS + (
    OSError,
    RuntimeError,
)
IPC_PEER_CLOSED_EXCEPTIONS: tuple[type[Exception], ...] = (
    BrokenPipeError,
    ConnectionResetError,
)


def _build_close_details(
    worker_id: int | None,
    details: Mapping[str, JSONValue] | None,
) -> JSONDict:
    close_details = dict(details or {})
    close_details["worker_id"] = worker_id
    return close_details


def is_ipc_peer_closed_exception(exception: BaseException) -> bool:
    return isinstance(exception, IPC_PEER_CLOSED_EXCEPTIONS)


async def close_ipc_writer(
    writer: asyncio.StreamWriter,
    *,
    worker_id: int | None,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    close_details = _build_close_details(worker_id, details)
    try:
        writer.close()
        await asyncio.wait_for(writer.wait_closed(), timeout=LOCAL_IO_TIMEOUT_SEC)
    except asyncio.CancelledError:
        raise
    except IPC_PEER_CLOSED_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="IPC writer was already closed by peer.",
            operation=OPERATION_CLOSE_CONNECTION,
            details=close_details,
            level="debug",
        )
    except IPC_CLOSE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to close IPC writer cleanly.",
            operation=OPERATION_CLOSE_CONNECTION,
            details=close_details,
            level="warning",
        )
