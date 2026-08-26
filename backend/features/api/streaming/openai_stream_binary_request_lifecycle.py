"""SoAI - OpenAI binary streaming task lifecycle helpers [backend/features/api/streaming/openai_stream_binary_request_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.responses import Response

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId
from core.types.json import JSONDict
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.runtime.openai_request_state import (
    apply_openai_api_key_quota_state,
    resolve_request_trace_id_optional,
)
from features.api.runtime.openai_task_failures import (
    handle_task_creation_failure,
)
from features.api.streaming.openai_stream_binary_request_components import (
    release_streaming_quota_reservation,
)

if TYPE_CHECKING:
    from fastapi import Request

    from features.api.runtime.context import ApiContext

__all__ = (
    "StreamingQuotaReservation",
    "create_binary_streaming_task_or_respond",
    "publish_request_event_or_respond",
    "resolve_streaming_binary_trace_id",
)

LOGGER_NAME = "SoAI.features.api.openai_stream_binary_request_lifecycle"
OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_CREATE_STREAMING_TASK = (
    "api_streaming.handle_streaming_binary_request.create_streaming_task"
)
OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_FINALIZE_AFTER_EXCEPTION = (
    "api_streaming.handle_streaming_binary_request.finalize_after_exception"
)
OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_FINALIZE_AFTER_SOAI_ERROR = (
    "api_streaming.handle_streaming_binary_request.finalize_after_soai_error"
)
OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_PUBLISH = (
    "api_streaming.handle_streaming_binary_request.publish"
)


def resolve_streaming_binary_trace_id(request: Request) -> str | None:
    return resolve_request_trace_id_optional(request)


@dataclass(frozen=True, slots=True)
class StreamingQuotaReservation:
    api_context: ApiContext
    trace_id: str | None
    key_id: str | None
    reservation: JSONDict | None

    def apply_to_request_state(self, request: Request) -> None:
        apply_openai_api_key_quota_state(
            request,
            key_id=self.key_id,
            reservation=self.reservation,
        )

    async def release(self, *, operation: str) -> None:
        await release_streaming_quota_reservation(
            self.api_context,
            self.key_id,
            self.reservation,
            trace_id=self.trace_id,
            operation=operation,
        )


async def create_binary_streaming_task_or_respond(
    *,
    api_context: ApiContext,
    context: RequestContext,
    registry: TaskRegistryProtocol,
    task_type: TaskTypeId,
    trace_id: str | None,
    quota: StreamingQuotaReservation,
    normalized_user_id: int,
    owner_id: str,
    cancellation_id: str,
    task_metadata: JSONDict,
    initial_status: TaskStatus,
    progress_total: int | None,
) -> Task | Response:
    try:
        task = await create(
            registry,
            task_type=task_type,
            user_id=normalized_user_id,
            owner_id=owner_id,
            owner_type="http_request",
            cancellation_id=cancellation_id,
            metadata=task_metadata,
            status=initial_status,
            progress_total=progress_total,
        )
        return task
    except asyncio.CancelledError:
        await quota.release(
            operation="api_streaming.handle_streaming_binary_request.create_streaming_task.cancelled.quota_release",
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        log_exception(
            logger,
            exception,
            message="Failed to create streaming binary task.",
            trace_id=trace_id,
            operation=OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_CREATE_STREAMING_TASK,
        )
        await quota.release(
            operation="api_streaming.handle_streaming_binary_request.create_streaming_task.quota_release",
        )
        return handle_task_creation_failure(
            exception,
            context,
            "api_streaming.handle_streaming_binary_request.create_streaming_task",
            api_context.dependencies.metrics_manager,
        )


async def publish_request_event_or_respond(
    *,
    api_context: ApiContext,
    registry: TaskRegistryProtocol,
    task_id: str,
    request_event: Event,
    quota: StreamingQuotaReservation,
) -> Response | None:
    trace_id = quota.trace_id
    try:
        await api_context.dependencies.event_bus.publish(request_event)
        return None
    except SoAIError as exception:
        logger = get_logger(LOGGER_NAME)
        log_exception(
            logger,
            exception,
            message="System event bus is not available.",
            trace_id=trace_id,
            operation=OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_PUBLISH,
            level="critical",
        )
        try:
            await finalize(
                registry,
                task_id,
                TaskStatus.FAILED,
                error_code=503,
                error_message="System event bus is not available.",
            )
        except RECOVERABLE_EXCEPTIONS as finalize_exception:
            log_handled_exception(
                logger,
                finalize_exception,
                message="Failed to finalize task after publish failure (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_FINALIZE_AFTER_SOAI_ERROR,
                details={"task_id": task_id},
                level="debug",
            )
        await quota.release(
            operation="api_streaming.handle_streaming_binary_request.publish.quota_release",
        )
        return build_openai_error_json_response(
            status_code=503,
            message="System event bus is not available.",
            canonical_error_type="server_error",
            param=None,
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        log_exception(
            logger,
            exception,
            message="Unhandled error while publishing streaming request.",
            trace_id=trace_id,
            operation=OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_PUBLISH,
        )
        try:
            await finalize(
                registry,
                task_id,
                TaskStatus.FAILED,
                error_code=500,
                error_message="Internal server error.",
            )
        except RECOVERABLE_EXCEPTIONS as cleanup_exception:
            log_handled_exception(
                logger,
                cleanup_exception,
                message="Task failure cleanup suppressed (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_API_STREAMING_HANDLE_STREAMING_BINARY_REQUEST_FINALIZE_AFTER_EXCEPTION,
                details={"task_id": task_id},
                level="debug",
            )
        await quota.release(
            operation="api_streaming.handle_streaming_binary_request.publish.quota_release",
        )
        return build_openai_error_json_response(
            status_code=500,
            message="Internal server error.",
            canonical_error_type="server_error",
            param=None,
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    except asyncio.CancelledError:
        await quota.release(
            operation="api_streaming.handle_streaming_binary_request.publish.cancelled.quota_release",
        )
        raise
