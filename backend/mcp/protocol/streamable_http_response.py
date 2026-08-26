"""SoAI - MCP Streamable HTTP response handling [backend/mcp/protocol/streamable_http_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import override

import httpx2

from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.serialization.json_parsing import parse_json_value
from core.streaming.sse_events import iter_sse_events
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_request_state import pop_pending_request
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.jsonrpc import (
    coerce_jsonrpc_id_to_int_for_lookup,
    resolve_pending_response,
)

__all__ = (
    "OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST",
    "MCPStreamAuthorizationError",
    "MCPStreamInsufficientScopeError",
    "raise_for_streamable_http_auth_status",
    "raise_for_streamable_http_send_status",
    "resolve_streamable_http_response_message",
)

OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST = "mcp.protocol.send_stream_request"


class MCPStreamAuthorizationError(ExternalServiceError):
    code: str | int = "mcp_authorization_required"
    http_status = 401
    is_transient = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        www_authenticate: str | None,
    ) -> None:
        super().__init__(
            message,
            details={
                "status_code": int(status_code),
                **({"www_authenticate": www_authenticate} if www_authenticate else {}),
            },
            operation=OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST,
        )

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (self.message,),
            {
                "status_code": (self.details or {}).get("status_code"),
                "www_authenticate": (self.details or {}).get("www_authenticate"),
            },
        )


class MCPStreamInsufficientScopeError(ExternalServiceError):
    code: str | int = "mcp_insufficient_scope"
    http_status = 403
    is_transient = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        www_authenticate: str | None,
    ) -> None:
        super().__init__(
            message,
            details={
                "status_code": int(status_code),
                **({"www_authenticate": www_authenticate} if www_authenticate else {}),
            },
            operation=OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST,
        )

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (self.message,),
            {
                "status_code": (self.details or {}).get("status_code"),
                "www_authenticate": (self.details or {}).get("www_authenticate"),
            },
        )


def raise_for_streamable_http_auth_status(
    status_code: int,
    www_authenticate: str | None,
) -> None:
    if status_code == 401:
        raise MCPStreamAuthorizationError(
            "MCP authorization required.",
            status_code=status_code,
            www_authenticate=www_authenticate,
        )
    if status_code == 403:
        raise MCPStreamInsufficientScopeError(
            "MCP insufficient scope.",
            status_code=status_code,
            www_authenticate=www_authenticate,
        )


def raise_for_streamable_http_send_status(response: httpx2.Response) -> None:
    status_code = int(response.status_code)
    raise_for_streamable_http_auth_status(
        status_code,
        response.headers.get("WWW-Authenticate"),
    )
    if status_code not in (200, 202):
        raise ExternalServiceError(
            f"MCP Streamable HTTP request failed (HTTP {status_code}).",
            details={"status_code": status_code},
            operation=OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST,
        )


async def resolve_streamable_http_response_message(
    *,
    response: httpx2.Response,
    connection: MCPServerConnection,
    message_id: int,
    future: asyncio.Future[JSONValue],
) -> None:
    content_type = (response.headers.get("content-type") or "").lower()
    if content_type.startswith("application/json"):
        payload = await _read_json_dict_or_none(response)
        if payload is not None:
            await _resolve_matching_payload(connection, message_id, future, payload)
        return
    if content_type.startswith("text/event-stream"):
        async for sse in iter_sse_events(response.aiter_lines()):
            if sse.event != "message" or not sse.data:
                continue
            try:
                decoded = parse_json_value(sse.data)
            except (ValidationError, TypeError):
                continue
            if isinstance(decoded, dict):
                matched = await _resolve_matching_payload(connection, message_id, future, decoded)
                if matched:
                    break


async def _read_json_dict_or_none(response: httpx2.Response) -> JSONDict | None:
    raw_bytes = await response.aread()
    if not raw_bytes:
        return None
    try:
        parsed = parse_json_value(raw_bytes)
    except (ValidationError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return dict(parsed)


async def _resolve_matching_payload(
    connection: MCPServerConnection,
    message_id: int,
    future: asyncio.Future[JSONValue],
    payload: JSONDict,
) -> bool:
    response_id = coerce_jsonrpc_id_to_int_for_lookup(payload.get("id"))
    if response_id != message_id:
        return False
    await pop_pending_request(connection.request_state, message_id)
    resolve_pending_response(future, payload)
    return True
