"""SoAI - Concurrent snapshot task handling for WebSocket events [backend/features/api/routes/system/events/websocket_snapshot_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.cancellation_ids import normalize_cancellation_id
from features.api.routes.system.events.snapshots.dispatcher import (
    handle_snapshot_request,
)
from features.api.routes.system.events.websocket_task_spawning import (
    create_managed_task,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("schedule_snapshot_request",)

LOGGER_NAME = "SoAI.features.api.websocket_snapshot_tasks"


def schedule_snapshot_request(
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    snapshot_key = _resolve_snapshot_task_key(data, runtime_context)

    async def run_snapshot_request() -> None:
        await handle_snapshot_request(
            data,
            runtime_context.connection,
            runtime_context.websocket,
        )

    task = create_managed_task(
        run_snapshot_request(),
        name=f"ws-snapshot-{snapshot_key}",
        logger=get_logger(LOGGER_NAME),
        cancellation_binder=runtime_context.api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=runtime_context.api_context.dependencies.task_finalizer_tracker,
        cancellation_id=_resolve_cancellation_id(runtime_context),
        owner="ws_snapshot_request",
    )
    runtime_context.connection.snapshot_tasks[snapshot_key] = task
    task.add_done_callback(
        _create_snapshot_task_discarder(runtime_context.connection.snapshot_tasks, snapshot_key),
    )


def _resolve_snapshot_task_key(
    data: JSONDict,
    runtime_context: WebsocketEventRuntimeContext,
) -> str:
    snapshot_id = data.get("snapshot_id")
    if isinstance(snapshot_id, str) and snapshot_id.strip():
        return create_system_id(
            subsystem="ws_snapshot",
            owner=snapshot_id.strip(),
            include_random_suffix=True,
        )
    return create_system_id(
        subsystem="ws_snapshot",
        owner=str(runtime_context.trace_id or "unknown"),
        include_random_suffix=True,
    )


def _resolve_cancellation_id(runtime_context: WebsocketEventRuntimeContext) -> str:
    try:
        context = runtime_context.request_adapter.state.context
    except AttributeError:
        context = None
    cancellation_id_value = context.cancellation_id if context is not None else None
    cancellation_id = normalize_cancellation_id(cancellation_id_value)
    if cancellation_id:
        return cancellation_id
    return create_system_id(
        subsystem="ws_snapshot",
        owner=str(runtime_context.trace_id or "unknown"),
        include_random_suffix=True,
    )


def _create_snapshot_task_discarder(
    snapshot_tasks: dict[str, asyncio.Task[None]],
    snapshot_key: str,
) -> Callable[[asyncio.Task[None]], None]:
    def discard_snapshot_task(completed_task: asyncio.Task[None]) -> None:
        if snapshot_tasks.get(snapshot_key) is completed_task:
            del snapshot_tasks[snapshot_key]

    return discard_snapshot_task
