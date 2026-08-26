"""SoAI - MCP inference and embedding request execution handlers [backend/mcp/registry/inference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_models_requests import InferenceRequestReceived
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.mcp.protocols_main import MCPServerProtocol
from core.openai.payload_validation import normalize_inference_payload_messages
from core.runtime.request_sources import REQUEST_SOURCE_OPENAI
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.inference_result_waiter import await_inference_result_from_queue
from mcp.registry.inference_task_failures import (
    finalize_inference_task_failed_noncritical,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.runtime.request_context import RequestContext
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = ("run_inference_payload",)

LOGGER_NAME = "SoAI.mcp.registry.inference"
OPERATION = "mcp.registry.publish_inference_event"


def _resolve_inference_effective_identity(
    manager: MCPServerProtocol,
    context: RequestContext,
    context_label: str,
) -> tuple[int, str, str]:
    session_user_id, session_client_id = manager.context.current_session_identity()
    try:
        context_user_id = context.user_id
    except AttributeError:
        context_user_id = 0
    effective_user_id = session_user_id if session_user_id > 0 else int(context_user_id or 0)
    effective_owner_type = "mcp_client" if effective_user_id > 0 else "system"
    effective_owner_id = session_client_id or context_label
    return effective_user_id, effective_owner_type, effective_owner_id


async def _create_inference_task(
    *,
    manager: MCPServerProtocol,
    context: RequestContext,
    context_label: str,
) -> tuple[Task, asyncio.Queue[Event], str | None]:
    task_registry = manager.task_registry
    effective_user_id, effective_owner_type, effective_owner_id = (
        _resolve_inference_effective_identity(manager, context, context_label)
    )
    task, reply_queue = await create_streaming_task(
        task_registry,
        task_type=TASK_TYPE_CHAT_COMPLETION,
        user_id=effective_user_id,
        owner_id=effective_owner_id,
        owner_type=effective_owner_type,
        cancellation_id=context.cancellation_id,
        initial_status=TaskStatus.QUEUED,
        metadata={
            "event_type": "mcp_inference_payload",
            "context_label": context_label,
        },
        request_source=REQUEST_SOURCE_OPENAI,
        delivery_mode="streaming",
    )
    context.task_id = task.task_id
    try:
        trace_id = context.trace_id
    except AttributeError:
        trace_id = None
    return task, reply_queue, trace_id


async def _publish_inference_request_or_raise(
    *,
    manager: MCPServerProtocol,
    context: RequestContext,
    payload: JSONDict,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> None:
    task_registry = manager.task_registry
    try:
        await manager.event_bus.publish(
            InferenceRequestReceived(
                context=context,
                payload=payload,
                reply_channel=reply_queue,
                task_id=task_id,
            ),
        )
    except SoAIError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to publish MCP inference event.",
            trace_id=trace_id,
            operation=OPERATION,
        )
        await finalize_inference_task_failed_noncritical(
            task_registry=task_registry,
            task_id=task_id,
            error_code=503,
            error_message="System event bus is not available.",
            logger=logger,
            trace_id=trace_id,
            operation="mcp.registry.inference.finalize_after_publish_failure",
        )
        raise MCPJSONRPCError(-32603, "System event bus is not available.") from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Unhandled error while publishing MCP inference event.",
            trace_id=trace_id,
            operation=OPERATION,
        )
        await finalize_inference_task_failed_noncritical(
            task_registry=task_registry,
            task_id=task_id,
            error_code=500,
            error_message="Internal error publishing inference event.",
            logger=logger,
            trace_id=trace_id,
            operation="mcp.registry.inference.finalize_after_publish_exception",
        )
        raise MCPJSONRPCError(-32603, "Internal server error.") from exception


async def run_inference_payload(
    manager: MCPServerProtocol,
    payload: JSONDict,
    context_label: str,
) -> JSONValue:
    logger = get_logger(LOGGER_NAME)
    session = manager.context.get_active_session()
    client_id = session.client_id if session else context_label
    session_id = session.session_id if session else None
    context = manager.context.build_request_context(
        client_id,
        session_id,
        context_label,
        context_label,
    )
    try:
        payload = normalize_inference_payload_messages(payload)
    except ValidationError as exception:
        raise MCPJSONRPCError(-32602, str(exception)) from exception
    task, reply_queue, trace_id = await _create_inference_task(
        manager=manager,
        context=context,
        context_label=context_label,
    )
    await _publish_inference_request_or_raise(
        manager=manager,
        context=context,
        payload=payload,
        reply_queue=reply_queue,
        task_id=task.task_id,
        logger=logger,
        trace_id=trace_id,
    )
    return await await_inference_result_from_queue(
        manager=manager,
        payload=payload,
        reply_queue=reply_queue,
        task_id=task.task_id,
        context=context,
        logger=logger,
        trace_id=trace_id,
    )
