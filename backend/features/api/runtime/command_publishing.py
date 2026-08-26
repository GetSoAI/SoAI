"""SoAI - Command construction and publishing for API dispatch [backend/features/api/runtime/command_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeGuard

from fastapi import Request

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from features.api.runtime.error_responses import handle_publish_error
from features.api.runtime.errors import raise_from_error_response
from features.api.runtime.internal_protocols import CommandConstructorProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("construct_and_publish_command",)

LOGGER_NAME = "SoAI.features.api.command_publishing"
OPERATION = "api_runtime.dispatch_and_respond"


def _is_command_constructor(command_type: type[Event]) -> TypeGuard[CommandConstructorProtocol]:
    if not issubclass(command_type, Event):
        return False
    try:
        fields = command_type.__dataclass_fields__
    except AttributeError:
        fields = None
    if not isinstance(fields, dict):
        return False
    return "reply_channel" in fields and "context" in fields


async def construct_and_publish_command(
    request: Request,
    event_bus: EventBusProtocol,
    registry: TaskRegistryProtocol,
    command_type: type[Event],
    task_id: str,
    reply_queue: asyncio.Queue[Event],
    command_fields: dict[str, JSONValue],
) -> tuple[Event, asyncio.Queue[Event]]:
    context = request.state.context
    if not _is_command_constructor(command_type):
        raise StateError(
            "Command dispatch requires a dataclass Event with reply_channel and context fields.",
        )
    cmd = command_type(reply_channel=reply_queue, context=context, **command_fields)
    cmd_trace_id = context.trace_id if isinstance(context, RequestContext) else None
    try:
        await event_bus.publish(cmd)
    except SoAIError as exception:
        error_response = await handle_publish_error(
            registry,
            task_id,
            exception,
            cmd_trace_id if isinstance(cmd_trace_id, str) else None,
            "api_runtime.CommandDispatcher.dispatch_and_respond",
            True,
            get_logger(LOGGER_NAME),
        )
        raise_from_error_response(request, error_response)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Unhandled error while publishing API runtime command.",
            trace_id=cmd_trace_id if isinstance(cmd_trace_id, str) else None,
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )
        error_response = await handle_publish_error(
            registry,
            task_id,
            exception,
            cmd_trace_id if isinstance(cmd_trace_id, str) else None,
            "api_runtime.CommandDispatcher.dispatch_and_respond",
            False,
            get_logger(LOGGER_NAME),
        )
        raise_from_error_response(request, error_response)
    return cmd, reply_queue
