"""SoAI - WebSocket chat runtime quota finalization [backend/features/api/runtime/chat_execution/runtime_quota.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from features.api.runtime.quota_reservation_finalization import (
    release_quota_reservation_required,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.logging.protocols import LoggerProtocol
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "release_locked_ws_chat_stream_runtime_quota_if_present",
    "release_ws_chat_stream_runtime_quota_if_present",
    "release_ws_chat_stream_runtime_quota_noncritical",
)

RUNTIME_QUOTA_RELEASE_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def release_locked_ws_chat_stream_runtime_quota_if_present(
    *,
    database_api_keys: DatabaseAPIKeysProtocol,
    runtime: AssistantTimelineRuntime,
    trace_id: str | None,
    operation: str,
) -> None:
    quota_key_id = runtime.quota_key_id
    quota_reservation = runtime.quota_token_reservation
    if quota_key_id is None or quota_reservation is None:
        return
    await release_quota_reservation_required(
        database_api_keys=database_api_keys,
        key_id=quota_key_id,
        reservation=quota_reservation,
        trace_id=trace_id,
        operation=operation,
    )
    runtime.clear_quota_reservation()


async def release_ws_chat_stream_runtime_quota_if_present(
    *,
    database_api_keys: DatabaseAPIKeysProtocol,
    runtime: AssistantTimelineRuntime,
    trace_id: str | None,
    operation: str,
) -> None:
    async with runtime.quota_release_lock:
        await release_locked_ws_chat_stream_runtime_quota_if_present(
            database_api_keys=database_api_keys,
            runtime=runtime,
            trace_id=trace_id,
            operation=operation,
        )


async def release_ws_chat_stream_runtime_quota_noncritical(
    *,
    database_api_keys: DatabaseAPIKeysProtocol,
    runtime: AssistantTimelineRuntime,
    logger: LoggerProtocol,
    trace_id: str | None,
    operation: str,
    message: str,
) -> None:
    try:
        await release_ws_chat_stream_runtime_quota_if_present(
            database_api_keys=database_api_keys,
            runtime=runtime,
            trace_id=trace_id,
            operation=operation,
        )
    except RUNTIME_QUOTA_RELEASE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message=message,
            trace_id=trace_id,
            operation=operation,
            level="warning",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )
