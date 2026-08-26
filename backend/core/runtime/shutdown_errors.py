"""SoAI - Shutdown exception classification helpers [backend/core/runtime/shutdown_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exceptions import ServiceUnavailableError, SoAIError
from core.tasks.cancellation_ids import normalize_cancellation_id

__all__ = (
    "SERVER_SHUTTING_DOWN_MESSAGE",
    "ServerShuttingDownError",
    "build_shutdown_task_cancelled_error",
    "is_shutdown_service_unavailable",
)

SERVER_SHUTTING_DOWN_MESSAGE = "Server shutting down."


class ServerShuttingDownError(ServiceUnavailableError): ...


def _iter_exception_chain(exception: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    pending: list[BaseException] = [exception]
    seen: set[int] = set()
    while pending:
        candidate = pending.pop()
        identity = id(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        chain.append(candidate)
        if isinstance(candidate, SoAIError) and isinstance(candidate.cause, BaseException):
            pending.append(candidate.cause)
        if isinstance(candidate.__cause__, BaseException):
            pending.append(candidate.__cause__)
        if isinstance(candidate.__context__, BaseException):
            pending.append(candidate.__context__)
    return chain


def is_shutdown_service_unavailable(
    exception: BaseException,
    shutdown_event: asyncio.Event | None,
) -> bool:
    if shutdown_event is None or not shutdown_event.is_set():
        return False
    for candidate in _iter_exception_chain(exception):
        if isinstance(candidate, ServerShuttingDownError):
            return True
    return False


def build_shutdown_task_cancelled_error(cancellation_id: str | None) -> TaskCancelledError:
    normalized_cancellation_id = normalize_cancellation_id(cancellation_id) or "system_shutdown"
    return TaskCancelledError(normalized_cancellation_id, SERVER_SHUTTING_DOWN_MESSAGE)
