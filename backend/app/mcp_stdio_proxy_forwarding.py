"""SoAI - MCP stdio proxy upstream forwarding loops [backend/app/mcp_stdio_proxy_forwarding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from app.mcp_stdio_proxy_backpressure import put_inbound_payload, put_stdout_line
from app.mcp_stdio_proxy_config import McpProxyConfig
from app.mcp_stdio_proxy_http import post_json
from core.errors.exceptions import StateError, ValidationError
from core.mcp.jsonrpc_messages import classify_jsonrpc_message
from core.mcp.mcp_2025_11_25 import MCP_PROTOCOL_VERSION_HEADER, MCP_SESSION_ID_HEADER
from core.mcp.protocol_versions import validate_protocol_version
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.streaming.sse_events import iter_sse_events
from core.types.json import is_json_dict
from core.validation.record_fields import require_json_object

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "McpProxyState",
    "inbound_worker",
    "sse_loop",
    "stdin_loop",
)


@dataclass(slots=True)
class McpProxyState:
    session_id: str | None
    protocol_version: str | None
    session_ready: asyncio.Event


def _resolve_initialize_protocol_version(payload: JSONDict) -> str:
    params = payload.get("params")
    if not is_json_dict(params):
        raise ValidationError("Initialize params.protocolVersion is required.")
    protocol_version_value = params.get("protocolVersion")
    if isinstance(protocol_version_value, str) and protocol_version_value.strip():
        valid, protocol_version = validate_protocol_version(protocol_version_value.strip())
        if valid:
            return protocol_version
        raise ValidationError(f"Unsupported protocol version: {protocol_version_value.strip()}")
    raise ValidationError("Initialize params.protocolVersion is required.")


def _resolve_response_protocol_version(parsed_response: JSONDict) -> str:
    result = parsed_response.get("result")
    if not is_json_dict(result):
        raise StateError("Upstream MCP initialize response is missing result.")
    protocol_version_value = result.get("protocolVersion")
    if not isinstance(protocol_version_value, str) or not protocol_version_value.strip():
        raise StateError("Upstream MCP initialize response is missing protocolVersion.")
    valid, protocol_version = validate_protocol_version(protocol_version_value.strip())
    if not valid:
        raise StateError("Upstream MCP initialize response has unsupported protocolVersion.")
    return protocol_version


async def _handle_inbound_message(
    client: httpx2.AsyncClient,
    config: McpProxyConfig,
    state: McpProxyState,
    stdout_queue: asyncio.Queue[str],
    payload: JSONDict,
) -> None:
    message_type = classify_jsonrpc_message(payload, require_jsonrpc_version=False).type
    if message_type == "invalid":
        raise ValidationError("Invalid JSON-RPC message.")
    is_initialize = message_type == "request" and payload.get("method") == "initialize"
    if is_initialize and state.session_id is not None:
        raise StateError("MCP session is already initialized.")
    session_id = state.session_id
    if session_id is None and not is_initialize:
        raise StateError("MCP session is not initialized.")
    protocol_version = (
        _resolve_initialize_protocol_version(payload) if is_initialize else state.protocol_version
    )
    if protocol_version is None:
        raise StateError("MCP session protocol version is not initialized.")
    response = await post_json(
        client,
        config.endpoint,
        token=config.token,
        session_id=None if is_initialize else session_id,
        protocol_version=protocol_version,
        payload=payload,
    )
    if message_type == "response":
        if response.status_code != 202:
            raise StateError("Upstream MCP response was not accepted.")
        return
    if message_type == "notification":
        if response.status_code != 202:
            raise StateError("Upstream MCP notification was not accepted.")
        return
    if response.status_code != 200:
        raise StateError("Upstream MCP request failed.")
    parsed_response = require_json_object(
        parse_json_value(response.text, field="Upstream MCP response"),
        label="Upstream MCP response",
        build_error=StateError,
        invalid_message="Upstream MCP response is not a JSON object.",
    )
    if is_initialize:
        next_session_id = response.headers.get(MCP_SESSION_ID_HEADER)
        if not isinstance(next_session_id, str) or not next_session_id:
            raise StateError("Missing MCP session id header on initialize response.")
        state.session_id = next_session_id
        state.protocol_version = _resolve_response_protocol_version(dict(parsed_response))
    await put_stdout_line(
        stdout_queue,
        serialize_json_compact_stable_strict(dict(parsed_response)),
    )
    if is_initialize:
        state.session_ready.set()


async def inbound_worker(
    inbound_queue: asyncio.Queue[JSONDict | None],
    client: httpx2.AsyncClient,
    config: McpProxyConfig,
    state: McpProxyState,
    stdout_queue: asyncio.Queue[str],
) -> None:
    while True:
        item = await inbound_queue.get()
        try:
            if item is None:
                return
            await _handle_inbound_message(client, config, state, stdout_queue, item)
        finally:
            inbound_queue.task_done()


async def stdin_loop(
    client: httpx2.AsyncClient,
    config: McpProxyConfig,
    state: McpProxyState,
    stdout_queue: asyncio.Queue[str],
    inbound_queue: asyncio.Queue[JSONDict | None],
) -> None:
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return
        stripped = line.strip()
        if not stripped:
            continue
        payload = require_json_object(
            parse_json_value(stripped, field="NDJSON input"),
            label="NDJSON input",
            build_error=ValidationError,
            invalid_message="NDJSON input must contain JSON objects.",
        )
        payload = dict(payload)
        message_type = classify_jsonrpc_message(payload, require_jsonrpc_version=False).type
        if message_type == "invalid":
            raise ValidationError("Invalid JSON-RPC message.")
        is_initialize = message_type == "request" and payload.get("method") == "initialize"
        if state.session_id is None:
            if not is_initialize:
                raise StateError("MCP session is not initialized. Send initialize first.")
            await _handle_inbound_message(client, config, state, stdout_queue, payload)
            continue
        await put_inbound_payload(inbound_queue, payload)


async def sse_loop(
    client: httpx2.AsyncClient,
    config: McpProxyConfig,
    state: McpProxyState,
    stdout_queue: asyncio.Queue[str],
) -> None:
    await state.session_ready.wait()
    session_id = state.session_id
    protocol_version = state.protocol_version
    if session_id is None:
        raise StateError("MCP session is not initialized.")
    if protocol_version is None:
        raise StateError("MCP session protocol version is not initialized.")
    headers: dict[str, str] = {
        "Authorization": f"Bearer {config.token}",
        "Accept": "text/event-stream",
        MCP_SESSION_ID_HEADER: session_id,
        MCP_PROTOCOL_VERSION_HEADER: protocol_version,
    }
    async with client.stream("GET", config.endpoint, headers=headers) as response:
        if response.status_code != 200:
            raise StateError("Upstream MCP SSE stream failed.")
        async for event in iter_sse_events(response.aiter_lines()):
            if event.event != "message":
                continue
            parsed_event = require_json_object(
                parse_json_value(event.data, field="Upstream MCP SSE message"),
                label="Upstream MCP SSE message",
                build_error=StateError,
                invalid_message="Upstream MCP SSE message is not a JSON object.",
            )
            await put_stdout_line(
                stdout_queue,
                serialize_json_compact_stable_strict(dict(parsed_event)),
            )
