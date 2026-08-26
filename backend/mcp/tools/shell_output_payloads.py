"""SoAI - MCP shell output response payload assembly [backend/mcp/tools/shell_output_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPToolRuntimeSessionStoreProtocol

__all__ = (
    "build_shell_incremental_output_payload",
    "build_shell_snapshot_output_payload",
)


def build_shell_incremental_output_payload(
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
    *,
    session_id: int,
    limit: int,
    exit_code: int | None,
    status: str | None,
) -> JSONDict:
    payload = runtime_sessions.read_shell_transcript_incremental(session_id, limit)
    payload["session_id"] = int(session_id)
    if exit_code is not None:
        payload["exit_code"] = int(exit_code)
    if status is not None:
        payload["status"] = status
    return payload


def build_shell_snapshot_output_payload(
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
    *,
    session_id: int,
    limit: int,
    exit_code: int | None,
    status: str | None,
) -> JSONDict:
    payload = runtime_sessions.snapshot_shell_transcript_page(session_id, limit)
    payload["session_id"] = int(session_id)
    if exit_code is not None:
        payload["exit_code"] = int(exit_code)
    if status is not None:
        payload["status"] = status
    return payload
