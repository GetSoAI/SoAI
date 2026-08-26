"""SoAI - Shared WebSocket OpenAI cancellation handler helpers [backend/features/api/routes/system/events/websocket_openai_cancel_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.types.json import JSONDict
from features.api.routes.system.events.websocket_openai_cancellation_parsing import (
    try_parse_openai_ws_cancel_request,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.internal_protocols import RuntimeWithLockProtocol

if TYPE_CHECKING:
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_openai_ws_cancel", "handle_openai_ws_cancel_with_lock")


async def handle_openai_ws_cancel[RuntimeT](
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    require_run_id: Callable[[JSONDict], str],
    runtimes: dict[str, RuntimeT],
    cancel_runtime: Callable[[RuntimeT, str], None],
    build_cancelled_event: Callable[[str, str], JSONDict],
    warn_label: str,
) -> None:
    parsed = try_parse_openai_ws_cancel_request(
        data,
        connection=connection,
        require_run_id=require_run_id,
    )
    if parsed is None:
        return
    run_id, reason = parsed
    runtime = runtimes.get(run_id)
    if runtime is None:
        return
    cancel_runtime(runtime, reason)
    if runtimes.get(run_id) is runtime:
        runtimes.pop(run_id, None)
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_cancelled_event(run_id, reason),
        warn_label,
    )


async def handle_openai_ws_cancel_with_lock[RuntimeT: RuntimeWithLockProtocol](
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    require_run_id: Callable[[JSONDict], str],
    runtimes: dict[str, RuntimeT],
    cancel_runtime: Callable[[RuntimeT, str], Awaitable[None]],
    build_cancelled_event: Callable[[str, str], JSONDict],
    warn_label: str,
) -> None:
    parsed = try_parse_openai_ws_cancel_request(
        data,
        connection=connection,
        require_run_id=require_run_id,
    )
    if parsed is None:
        return
    run_id, reason = parsed
    runtime = runtimes.get(run_id)
    if runtime is None:
        return
    async with runtime.lock:
        if runtimes.get(run_id) is not runtime:
            return
        await cancel_runtime(runtime, reason)
        if runtimes.get(run_id) is runtime:
            runtimes.pop(run_id, None)
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_cancelled_event(run_id, reason),
        warn_label,
    )
