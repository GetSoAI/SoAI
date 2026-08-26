"""SoAI - MCP runtime shell transcript methods [backend/mcp/tools/runtime_session_transcript_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError
from mcp.tools.runtime_session_shell_methods import touch_shell_session
from mcp.tools.shell_transcript_store import ShellTranscript, build_empty_shell_output_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPToolRuntimeSessionShellStoreProtocol

__all__ = (
    "append_shell_transcript_output",
    "create_shell_transcript",
    "read_shell_transcript_incremental",
    "read_shell_transcript_lines",
    "remove_shell_transcript",
    "search_shell_transcript",
    "snapshot_shell_transcript_page",
)


def create_shell_transcript(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    transcript_root: str,
) -> None:
    session = self.shell_sessions.get(session_id)
    if session is None:
        raise MCPToolError(-32602, f"Unknown session_id: {session_id}")
    transcript_dir = os.path.join(transcript_root, str(session_id))
    transcript_path = os.path.join(transcript_dir, "output.bin")
    self.shell_transcripts[session_id] = ShellTranscript(path=transcript_path)


def append_shell_transcript_output(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    data: bytes,
) -> None:
    transcript = self.shell_transcripts.get(session_id)
    if transcript is None:
        return
    transcript.append(data)


def read_shell_transcript_incremental(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    limit: int,
) -> JSONDict:
    session = self.shell_sessions.get(session_id)
    if session is not None:
        touch_shell_session(session)
    transcript = self.shell_transcripts.get(session_id)
    if transcript is None:
        return build_empty_shell_output_payload(limit=limit)
    return transcript.read_incremental(limit=limit)


def snapshot_shell_transcript_page(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    limit: int,
) -> JSONDict:
    session = self.shell_sessions.get(session_id)
    if session is not None:
        touch_shell_session(session)
    transcript = self.shell_transcripts.get(session_id)
    if transcript is None:
        return build_empty_shell_output_payload(limit=limit)
    return transcript.snapshot_page(limit=limit)


def read_shell_transcript_lines(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    offset: int,
    limit: int,
    from_end: bool,
) -> JSONDict:
    session = self.shell_sessions.get(session_id)
    if session is None:
        raise MCPToolError(-32602, f"Unknown session_id: {session_id}")
    touch_shell_session(session)
    transcript = self.shell_transcripts.get(session_id)
    if transcript is None:
        return build_empty_shell_output_payload(limit=limit)
    return transcript.read_lines(offset=offset, limit=limit, from_end=from_end)


def search_shell_transcript(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    query: str,
    offset: int,
    limit: int,
    case_sensitive: bool,
) -> JSONDict:
    session = self.shell_sessions.get(session_id)
    if session is None:
        raise MCPToolError(-32602, f"Unknown session_id: {session_id}")
    touch_shell_session(session)
    transcript = self.shell_transcripts.get(session_id)
    if transcript is None:
        return {
            "query": query,
            "offset": offset,
            "limit": limit,
            "total_lines": 0,
            "returned_matches": 0,
            "next_offset": None,
            "has_more": False,
            "transcript_truncated": False,
            "matches": [],
        }
    return transcript.search(
        query=query,
        offset=offset,
        limit=limit,
        case_sensitive=case_sensitive,
    )


def remove_shell_transcript(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
) -> None:
    transcript = self.shell_transcripts.pop(session_id, None)
    if transcript is None:
        return
    transcript.remove()
