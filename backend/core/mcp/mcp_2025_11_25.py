"""SoAI - MCP 2025-11-25 protocol contract [backend/core/mcp/mcp_2025_11_25.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "JSON_RPC_VERSION",
    "MCP_CAPABILITY_COMPLETIONS",
    "MCP_CAPABILITY_ELICITATION",
    "MCP_CAPABILITY_LOGGING",
    "MCP_CAPABILITY_PROMPTS",
    "MCP_CAPABILITY_RESOURCES",
    "MCP_CAPABILITY_ROOTS",
    "MCP_CAPABILITY_SAMPLING",
    "MCP_CAPABILITY_TASKS",
    "MCP_CAPABILITY_TOOLS",
    "MCP_FEATURE_STREAMABLE_HTTP",
    "MCP_PROTOCOL_VERSION",
    "MCP_PROTOCOL_VERSION_HEADER",
    "MCP_SESSION_ID_HEADER",
    "SESSION_ID_REGEX",
    "validate_jsonrpc_id",
    "validate_jsonrpc_id_for_request",
    "validate_jsonrpc_id_str_or_int",
    "validate_session_id_format",
)

MCP_PROTOCOL_VERSION: str = "2025-11-25"

MCP_SESSION_ID_HEADER: str = "mcp-session-id"
MCP_PROTOCOL_VERSION_HEADER: str = "mcp-protocol-version"
JSON_RPC_VERSION: str = "2.0"
SESSION_ID_REGEX: str = r"^[\x21-\x7E]+$"

MCP_CAPABILITY_TOOLS: str = "tools"
MCP_CAPABILITY_RESOURCES: str = "resources"
MCP_CAPABILITY_PROMPTS: str = "prompts"
MCP_CAPABILITY_LOGGING: str = "logging"
MCP_CAPABILITY_COMPLETIONS: str = "completions"
MCP_CAPABILITY_TASKS: str = "tasks"
MCP_CAPABILITY_ROOTS: str = "roots"
MCP_CAPABILITY_SAMPLING: str = "sampling"
MCP_CAPABILITY_ELICITATION: str = "elicitation"
MCP_FEATURE_STREAMABLE_HTTP: str = "streamable_http"


def validate_session_id_format(session_id: str) -> bool:
    return re.fullmatch(SESSION_ID_REGEX, session_id) is not None


def validate_jsonrpc_id(rpc_id: JSONValue) -> tuple[bool, str | int | None]:
    if rpc_id is None:
        return (True, None)
    return validate_jsonrpc_id_str_or_int(rpc_id)


def validate_jsonrpc_id_str_or_int(rpc_id: JSONValue) -> tuple[bool, str | int | None]:
    if isinstance(rpc_id, str):
        return (True, rpc_id)
    if isinstance(rpc_id, int) and (not isinstance(rpc_id, bool)):
        return (True, rpc_id)
    return (False, None)


def validate_jsonrpc_id_for_request(rpc_id: JSONValue) -> tuple[bool, str | int | None]:
    return validate_jsonrpc_id_str_or_int(rpc_id)
