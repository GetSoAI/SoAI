"""SoAI - WebSocket message handlers for system events channel [backend/features/api/routes/system/events/websocket_message_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from features.api.routes.system.events.websocket_log_stream.streams import (
    start_log_stream,
    stop_log_stream,
)
from features.api.routes.system.events.websocket_subscription_validation import (
    require_history_limit,
    require_source_name,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_log_stream_subscribe_message",
    "handle_log_stream_unsubscribe_message",
    "resolve_pty_cols_rows",
)


async def handle_log_stream_subscribe_message(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    shutdown_event: asyncio.Event,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    source_name = await require_source_name(
        data,
        enqueue_warning_tracker=enqueue_warning_tracker,
        connection=connection,
        trace_id=trace_id,
        action="subscribe_log_stream",
    )
    if source_name is None:
        return
    history_limit = await require_history_limit(
        data,
        enqueue_warning_tracker=enqueue_warning_tracker,
        connection=connection,
        trace_id=trace_id,
    )
    if "history_limit" in data and history_limit is None:
        return
    await start_log_stream(
        source_name,
        connection=connection,
        shutdown_event=shutdown_event,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        history_limit=history_limit,
    )


async def handle_log_stream_unsubscribe_message(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    source_name = await require_source_name(
        data,
        enqueue_warning_tracker=enqueue_warning_tracker,
        connection=connection,
        trace_id=trace_id,
        action="unsubscribe_log_stream",
    )
    if source_name is None:
        return
    await stop_log_stream(
        source_name,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
    )


def resolve_pty_cols_rows(
    data: JSONDict,
    *,
    default_cols: int,
    default_rows: int,
) -> tuple[int, int]:
    cols_value = data.get("cols")
    rows_value = data.get("rows")
    cols = cols_value if is_strict_int(cols_value) else default_cols
    rows = rows_value if is_strict_int(rows_value) else default_rows
    return int(cols), int(rows)
