"""SoAI - Model action operation helpers [backend/models/actions/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.progress.percent import coerce_percent_or_default
from core.runtime.protocols import RequestOwnershipContextProtocol
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_system_id, extend_soai_id
from core.tasks.api_events import send_task_progress_event
from core.tasks.protocols import TaskRegistryProtocol
from core.types.json import JSONValue
from models.actions.task_creation import (
    create_reply_bound_model_action_task,
    create_streaming_model_action_task,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "create_delete_task_if_needed",
    "create_purge_delete_context",
    "execute_model_file_deletion",
)


def _coerce_progress_message(value: JSONValue) -> str:
    return value if isinstance(value, str) else ""


async def execute_model_file_deletion(
    plugin_instance: PluginInstanceProtocol,
    model_info: JSONDict,
    reply_channel: asyncio.Queue[Event],
    shutdown_event: asyncio.Event,
    task_registry: TaskRegistryProtocol,
) -> tuple[bool, str | None]:
    async def progress_callback(progress_payload: JSONDict) -> None:
        percent_value = coerce_percent_or_default(progress_payload.get("percent"), default=0)
        message_value = _coerce_progress_message(progress_payload.get("message"))
        details_value = _coerce_progress_message(progress_payload.get("details"))
        await send_task_progress_event(
            reply_channel,
            percent=percent_value,
            message=message_value,
            details=details_value,
            registry=task_registry,
        )

    try:
        return await plugin_instance.delete_model(model_info, progress_callback, shutdown_event)
    except asyncio.CancelledError:
        shutdown_event.set()
        raise


async def create_delete_task_if_needed(
    reply_channel: asyncio.Queue[Event],
    context: RequestOwnershipContextProtocol | None,
    universal_id: str,
    task_registry: TaskRegistryProtocol,
) -> str | None:
    return await create_reply_bound_model_action_task(
        task_registry,
        reply_channel,
        context,
        metadata={
            "operation": "model_delete",
            "universal_id": universal_id,
        },
    )


async def create_purge_delete_context(
    command_context: RequestOwnershipContextProtocol | None,
    plugin_name: str,
    universal_id: str,
    task_registry: TaskRegistryProtocol,
) -> tuple[RequestContext, asyncio.Queue[Event]]:
    task, reply_queue, ownership = await create_streaming_model_action_task(
        task_registry,
        command_context,
        metadata={
            "operation": "purge_model_delete",
            "plugin_name": plugin_name,
            "universal_id": universal_id,
        },
    )
    delete_trace_id = command_context.trace_id if command_context is not None else None
    delete_client_ip = command_context.client_ip if command_context is not None else None
    if not delete_trace_id:
        delete_trace_id = create_system_id(
            subsystem="model_purge",
            owner=plugin_name,
            include_random_suffix=True,
        )
    else:
        delete_trace_id = extend_soai_id(delete_trace_id, ("model_purge", plugin_name))
    delete_context = RequestContext(
        trace_id=extend_soai_id(delete_trace_id, ("purge_delete", universal_id)),
        client_ip=delete_client_ip,
        user_id=ownership.user_id,
        task_id=task.task_id,
        cancellation_id=task.cancellation_id,
    )
    return delete_context, reply_queue
