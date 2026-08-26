"""SoAI - Model Context Protocol JSON-RPC helpers [backend/mcp/protocol/jsonrpc.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.mcp.mcp_2025_11_25 import JSON_RPC_VERSION
from core.mcp.protocol_versions import SUPPORTED_PROTOCOL_VERSIONS
from core.meta.versioning import get_core_version
from core.types.json_value import coerce_json_dict, is_json_value
from core.validation.integers import is_strict_int
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_core_app_info",
    "build_jsonrpc_notification",
    "build_jsonrpc_request",
    "coerce_jsonrpc_id_to_int_for_lookup",
    "get_preferred_protocol_versions",
    "is_protocol_version_error",
    "resolve_pending_response",
)


def coerce_jsonrpc_id_to_int_for_lookup(value: JSONValue) -> int | None:
    if is_strict_int(value):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        if value == "0" or value[0] != "0":
            return int(value)
    return None


def build_core_app_info() -> JSONDict:
    info: JSONDict = {"name": "SoAI"}
    try:
        info["version"] = get_core_version()
    except (StateError, ValidationError):
        info["version"] = "unknown"
    return info


def build_jsonrpc_request(message_id: int, method: str, params: JSONDict) -> JSONDict:
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "id": message_id,
        "method": method,
        "params": params,
    }


def build_jsonrpc_notification(method: str, params: JSONDict | None = None) -> JSONDict:
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "method": method,
        **({"params": params} if params else {}),
    }


def get_preferred_protocol_versions() -> tuple[str, ...]:
    return tuple(reversed(SUPPORTED_PROTOCOL_VERSIONS))


def is_protocol_version_error(error: MCPJSONRPCError) -> bool:
    message = error.message.lower()
    return error.rpc_code in (-32600, -32602) and ("protocol" in message or "version" in message)


def resolve_pending_response(future: asyncio.Future[JSONValue], message: JSONDict) -> None:
    if future.done():
        return
    if "error" in message:
        error_payload: JSONDict = coerce_json_dict(message.get("error")) or {}
        code = (
            _coerce_jsonrpc_error_code(error_payload["code"]) if "code" in error_payload else -32603
        )
        message_value = error_payload.get("message")
        message_text = str(message_value) if message_value is not None else "Unknown error"
        data_value = error_payload.get("data")
        future.set_exception(
            MCPJSONRPCError(
                code,
                message_text,
                data_value if is_json_value(data_value) else None,
            ),
        )
        return
    future.set_result(message.get("result"))


def _coerce_jsonrpc_error_code(value: JSONValue) -> int:
    if isinstance(value, bool):
        raise ValidationError("JSON-RPC error code must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValidationError("JSON-RPC error code must be an integer.")
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exception:
            raise ValidationError("JSON-RPC error code must be an integer.") from exception
    raise ValidationError("JSON-RPC error code must be an integer.")
