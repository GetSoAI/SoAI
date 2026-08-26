"""SoAI - MCP core data types [backend/core/mcp/runtime_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

__all__ = (
    "ShellSession",
    "FileReadStamp",
    "FileSignature",
    "ToolWorkspaceState",
)


@dataclass(slots=True)
class ShellSession:
    session_id: int
    terminal_session_id: str
    owner_key: str
    user_id: int
    run_in_background: bool = False
    background_watch_started: bool = False
    terminal_session_finalized: bool = False
    stdin_buffer: str = ""
    stdin_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    created_at: float = field(default_factory=time.time)
    last_touched_monotonic: float = field(default_factory=time.monotonic)
    exit_code: int | None = None
    output: deque[bytes] = field(default_factory=deque[bytes])
    output_bytes: int = 0
    output_start_sequence: int = 0
    output_next_sequence: int = 0
    output_drain_sequence: int = 0


@dataclass(frozen=True, slots=True)
class FileSignature:
    dev: int
    inode: int
    mtime_ns: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class FileReadStamp:
    signature: FileSignature
    read_at_epoch_sec: float


@dataclass(slots=True)
class ToolWorkspaceState:
    workspace_path: str | None
    last_touched_monotonic: float = field(default_factory=time.monotonic)
    file_read_stamps: dict[str, FileReadStamp] = field(default_factory=dict[str, FileReadStamp])
