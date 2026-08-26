"""SoAI - MCP server-mode streaming helpers [backend/features/api/routes/mcp/routes/server_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from core.errors.external_service_exception import MCPError
from core.logging.trace import get_logger
from core.mcp.protocols_main import MCPServerProtocol
from core.serialization.json import serialize_json_compact_stable
from core.streaming.sse_frames import (
    format_sse_heartbeat_frame,
    format_sse_named_data_frame,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "encode_mcp_sse_message",
    "format_mcp_sse_message",
    "mcp_notification_stream",
    "streamable_http_single_message_stream",
)

LOGGER_NAME = "SoAI.features.api.server_streaming"


STREAMABLE_HTTP_SSE_PREAMBLE: tuple[str, ...] = ("retry: 5000\n\n",)


def format_mcp_sse_message(event_id: str, payload: JSONDict) -> str:
    data = serialize_json_compact_stable(payload)
    return format_sse_named_data_frame(
        serialized_payload=data,
        event_name="message",
        event_id=event_id,
    )


async def encode_mcp_sse_message(
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    payload: JSONDict,
) -> str:
    event_id = await mcp_server_instance.streaming.allocate_sse_event_id(session_id, payload)
    return format_mcp_sse_message(event_id, payload)


async def mcp_notification_stream(
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    preamble: tuple[str, ...],
    last_event_id: str | None = None,
    shutdown_events: tuple[asyncio.Event, ...] = (),
) -> AsyncGenerator[str]:
    logger = get_logger(LOGGER_NAME)
    for chunk in preamble:
        yield chunk
    if last_event_id and (
        not await mcp_server_instance.streaming.has_active_client_stream(session_id)
    ):
        for (
            event_id,
            payload,
        ) in await mcp_server_instance.streaming.get_sse_replay_events(session_id, last_event_id):
            yield format_mcp_sse_message(event_id, payload)
    try:
        async for notification in mcp_server_instance.streaming.get_client_notification_stream(
            session_id,
            shutdown_events=shutdown_events,
        ):
            if notification is None:
                yield format_sse_heartbeat_frame()
                continue
            yield await encode_mcp_sse_message(mcp_server_instance, session_id, notification)
    except MCPError as exception:
        logger.debug(
            "MCP notification stream ended with protocol error: code=%s message=%s",
            exception.rpc_code,
            exception.message,
        )


async def streamable_http_single_message_stream(
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    payload: JSONDict,
) -> AsyncGenerator[str]:
    for chunk in STREAMABLE_HTTP_SSE_PREAMBLE:
        yield chunk
    yield await encode_mcp_sse_message(mcp_server_instance, session_id, payload)
