"""SoAI - MCP shell-session output streaming helpers [backend/mcp/tools/shell_session_output_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.text_delta_chunking import (
    DEFAULT_EVENT_TEXT_DELTA_MAX_CHARS,
    split_text_delta,
)
from core.events.types_conversation import ToolCallOutputDeltaEvent
from core.timing.constants import ASYNC_POLL_SLICE_SEC
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from mcp.tools.internal_protocols import MCPToolRuntimeSessionStoreProtocol

__all__ = (
    "ShellSessionOutputDrainResult",
    "drain_shell_session_output_for_interval",
    "publish_shell_session_output_delta",
)

_STREAM_DRAIN_MAX_CHARS: int = 64_000
_STREAM_EVENT_MAX_CHARS: int = DEFAULT_EVENT_TEXT_DELTA_MAX_CHARS


@dataclass(frozen=True, slots=True)
class ShellSessionOutputDrainResult:
    output: str
    exit_code: int | None


@dataclass(frozen=True, slots=True)
class _OutputDrainContext:
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol
    event_bus: EventBusProtocol
    identity: CurrentToolCallIdentity | None
    tool_name: str
    shell_session_id: int
    max_return_chars: int


@dataclass(frozen=True, slots=True)
class _OutputDrainStep:
    has_output: bool
    returned_chars: int


def publish_shell_session_output_delta(
    *,
    event_bus: EventBusProtocol,
    identity: CurrentToolCallIdentity | None,
    tool_name: str,
    delta: str,
) -> None:
    if not delta:
        return
    if identity is None or identity.tool_name != tool_name:
        return
    for chunk in split_text_delta(delta, max_chunk_chars=_STREAM_EVENT_MAX_CHARS):
        event_bus.try_publish_nowait(
            ToolCallOutputDeltaEvent(
                user_id=identity.user_id,
                conv_id=identity.conv_id,
                message_index=identity.message_index,
                turn_id=identity.turn_id,
                iteration_index=identity.iteration_index,
                call_id=identity.call_id,
                tool_name=identity.tool_name,
                delta=chunk,
            ),
        )


def _append_returned_output(
    *,
    returned_chunks: list[str],
    returned_chars: int,
    drained: str,
    max_return_chars: int,
) -> int:
    if returned_chars >= max_return_chars:
        return returned_chars
    remaining = max_return_chars - returned_chars
    slice_text = drained[:remaining]
    if slice_text:
        returned_chunks.append(slice_text)
        return returned_chars + len(slice_text)
    return returned_chars


def _join_output(chunks: list[str]) -> str:
    return chunks[0] if len(chunks) == 1 else "".join(chunks)


def _publish_and_capture_drained_output(
    *,
    context: _OutputDrainContext,
    drained: str,
    returned_chunks: list[str],
    returned_chars: int,
) -> int:
    publish_shell_session_output_delta(
        event_bus=context.event_bus,
        identity=context.identity,
        tool_name=context.tool_name,
        delta=drained,
    )
    return _append_returned_output(
        returned_chunks=returned_chunks,
        returned_chars=returned_chars,
        drained=drained,
        max_return_chars=context.max_return_chars,
    )


def _drain_publish_and_capture_output(
    context: _OutputDrainContext,
    *,
    returned_chunks: list[str],
    returned_chars: int,
) -> _OutputDrainStep:
    drained = context.runtime_sessions.drain_shell_output(
        context.shell_session_id,
        _STREAM_DRAIN_MAX_CHARS,
    )
    if not drained:
        return _OutputDrainStep(has_output=False, returned_chars=returned_chars)
    next_returned_chars = _publish_and_capture_drained_output(
        context=context,
        drained=drained,
        returned_chunks=returned_chunks,
        returned_chars=returned_chars,
    )
    return _OutputDrainStep(has_output=True, returned_chars=next_returned_chars)


async def drain_shell_session_output_for_interval(
    *,
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
    event_bus: EventBusProtocol,
    identity: CurrentToolCallIdentity | None,
    tool_name: str,
    shell_session_id: int,
    wait_ms: int,
    max_return_chars: int,
) -> ShellSessionOutputDrainResult:
    return await _drain_context_output_for_interval(
        _OutputDrainContext(
            runtime_sessions,
            event_bus,
            identity,
            tool_name,
            shell_session_id,
            max_return_chars,
        ),
        wait_ms=wait_ms,
    )


async def _drain_context_output_for_interval(
    drain_context: _OutputDrainContext,
    *,
    wait_ms: int,
) -> ShellSessionOutputDrainResult:
    runtime_sessions = drain_context.runtime_sessions
    shell_session_id = drain_context.shell_session_id
    returned_chunks: list[str] = []
    returned_chars = 0
    deadline_ms = monotonic_ms() + max(0, wait_ms)
    exit_code: int | None = None
    while True:
        drain_step = _drain_publish_and_capture_output(
            drain_context,
            returned_chunks=returned_chunks,
            returned_chars=returned_chars,
        )
        returned_chars = drain_step.returned_chars
        session_after = runtime_sessions.get_shell_session(shell_session_id)
        exit_code = session_after.exit_code if session_after is not None else None
        if exit_code is not None or monotonic_ms() >= deadline_ms:
            break
        await asyncio.sleep(ASYNC_POLL_SLICE_SEC)
    while True:
        drain_step = _drain_publish_and_capture_output(
            drain_context,
            returned_chunks=returned_chunks,
            returned_chars=returned_chars,
        )
        returned_chars = drain_step.returned_chars
        if not drain_step.has_output:
            break
    return ShellSessionOutputDrainResult(output=_join_output(returned_chunks), exit_code=exit_code)
