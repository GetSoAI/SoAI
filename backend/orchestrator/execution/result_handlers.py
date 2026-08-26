"""SoAI - Execution result handling helpers [backend/orchestrator/execution/result_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import (
    ApiError,
    ConfigurationError,
    IpcRemoteRequestError,
    SoAITimeoutError,
    ValidationError,
)
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from orchestrator.execution.result_processing_error import ResultProcessingError
from orchestrator.execution.streaming import InvalidStreamingChunk
from orchestrator.execution.streaming_completion import StreamingCompletion

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.execution.internal_protocols import ResultProcessorProtocol

__all__ = (
    "buffer_stream_to_result",
    "handle_streaming_result",
    "handle_unary_result",
)

_RESULT_EXCEPTION_PASSTHROUGH_TYPES: tuple[type[BaseException], ...] = (
    httpx2.HTTPError,
    ApiError,
    ExternalServiceError,
    IpcRemoteRequestError,
    SoAITimeoutError,
    ValidationError,
    ConfigurationError,
    InvalidStreamingChunk,
)


def _should_passthrough_result_exception(exception: BaseException) -> bool:
    return isinstance(exception, _RESULT_EXCEPTION_PASSTHROUGH_TYPES)


def handle_unary_result(
    results: ResultProcessorProtocol,
    task: Task,
    model_info: JSONDict,
    result_payload: JSONDict,
    *,
    plugin_name: str = "",
) -> JSONDict:
    try:
        return results.handle_unary_result(
            task,
            model_info,
            result_payload,
            plugin_name=plugin_name,
        )
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        if _should_passthrough_result_exception(exception):
            raise
        raise ResultProcessingError(
            f"Failed to process unary result: {exception}",
            cause=exception,
            operation="orchestrator.result_processing.unary",
            details={"task_id": task.task_id},
        ) from exception


async def handle_streaming_result(
    results: ResultProcessorProtocol,
    task: Task,
    model_info: JSONDict,
    result: AsyncIterable[StreamChunk],
    *,
    usage_reporting_requested: bool,
    plugin_name: str = "",
) -> StreamingCompletion | JSONDict | None:
    try:
        return await results.handle_streaming_result(
            task,
            model_info,
            result,
            usage_reporting_requested=usage_reporting_requested,
            plugin_name=plugin_name,
        )
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        if _should_passthrough_result_exception(exception):
            raise
        raise ResultProcessingError(
            f"Failed to process streaming result: {exception}",
            cause=exception,
            operation="orchestrator.result_processing.streaming",
            details={"task_id": task.task_id},
        ) from exception


async def buffer_stream_to_result(
    results: ResultProcessorProtocol,
    task: Task,
    model_info: JSONDict,
    result: AsyncIterable[StreamChunk],
    *,
    plugin_name: str = "",
) -> JSONDict:
    try:
        return await results.buffer_stream_to_result(
            task,
            model_info,
            result,
            plugin_name=plugin_name,
        )
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        if _should_passthrough_result_exception(exception):
            raise
        raise ResultProcessingError(
            f"Failed to buffer stream result: {exception}",
            cause=exception,
            operation="orchestrator.result_processing.buffer",
            details={"task_id": task.task_id},
        ) from exception
