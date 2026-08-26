"""SoAI - Background shell-session watch loop and finalization [backend/mcp/tools/shell_background/watcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.constants import ASYNC_POLL_SLICE_SEC
from core.timing.monotonic import monotonic_ms
from core.tool_calls.deferred_tool_call_streamer import (
    DeferredToolCallDependencies,
    DeferredToolCallStreamer,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)
from mcp.tools.shell_output_payloads import build_shell_snapshot_output_payload
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    close_shell_session_resources,
    require_shell_terminal_session_finalized,
)

if TYPE_CHECKING:
    from core.terminal.protocols import TerminalServiceProtocol
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from core.types.json import JSONValue
    from mcp.tools.internal_protocols import MCPToolRuntimeSessionStoreProtocol

__all__ = (
    "ShellBackgroundWatch",
    "run_background_shell_watch",
)

OPERATION_SHELL_BACKGROUND_WATCH = "mcp.tools.shell_background.watch"


@dataclass(frozen=True, slots=True)
class ShellBackgroundWatch:
    streamer_deps: DeferredToolCallDependencies
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol
    terminal: TerminalServiceProtocol
    identity: CurrentToolCallIdentity
    shell_session_id: int
    terminal_session_id: str
    tty: bool
    max_output_chars: int
    output_limit: int
    started_ms: int


def _elapsed_ms(started_ms: int) -> int:
    return max(0, monotonic_ms() - started_ms)


def _snapshot_result(watch: ShellBackgroundWatch, exit_code: int | None) -> JSONValue:
    return build_shell_snapshot_output_payload(
        watch.runtime_sessions,
        session_id=watch.shell_session_id,
        limit=watch.output_limit,
        exit_code=exit_code,
        status=None,
    )


async def _cleanup_watch_session(
    watch: ShellBackgroundWatch,
    *,
    retain_runtime_session: bool,
) -> None:
    cleanup_deps = ShellSessionCleanupDeps(
        runtime_sessions=watch.runtime_sessions,
        terminal=watch.terminal,
        logger=watch.streamer_deps.logger,
    )
    if retain_runtime_session:
        await require_shell_terminal_session_finalized(
            cleanup_deps,
            operation=OPERATION_SHELL_BACKGROUND_WATCH,
            shell_session_id=watch.shell_session_id,
            terminal_session_id=watch.terminal_session_id,
        )
        return
    await close_shell_session_resources(
        cleanup_deps,
        operation=OPERATION_SHELL_BACKGROUND_WATCH,
        shell_session_id=watch.shell_session_id,
        terminal_session_id=watch.terminal_session_id,
    )


async def _wait_for_exit(watch: ShellBackgroundWatch) -> int | None:
    exit_code: int | None = None
    while True:
        exists, exit_code = watch.runtime_sessions.peek_shell_session_exit(watch.shell_session_id)
        if not exists or exit_code is not None:
            return exit_code
        await asyncio.sleep(ASYNC_POLL_SLICE_SEC)


async def _finalize_watch(
    watch: ShellBackgroundWatch,
    streamer: DeferredToolCallStreamer,
    *,
    status: str,
    error_message: str | None,
    exit_code: int | None,
    cancellation_safe: bool,
) -> None:
    finalize_call = streamer.finalize(
        status=status,
        duration_ms=_elapsed_ms(watch.started_ms),
        error_message=error_message,
        result_payload=_snapshot_result(watch, exit_code),
    )
    if cancellation_safe:
        await uncancel_then_cleanup(finalize_call)
        return
    await finalize_call


async def run_background_shell_watch(watch: ShellBackgroundWatch) -> str:
    streamer = DeferredToolCallStreamer(deps=watch.streamer_deps)
    retain_runtime_session = False
    try:
        exit_code = await _wait_for_exit(watch)
        await _finalize_watch(
            watch,
            streamer,
            status=TOOL_CALL_STATUS_COMPLETED,
            error_message=None,
            exit_code=exit_code,
            cancellation_safe=False,
        )
        retain_runtime_session = True
        return TOOL_CALL_STATUS_COMPLETED
    except asyncio.CancelledError:
        await _finalize_watch(
            watch,
            streamer,
            status=TOOL_CALL_STATUS_CANCELLED,
            error_message="Shell cancelled.",
            exit_code=None,
            cancellation_safe=True,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_SHELL_BACKGROUND_WATCH,
        )
        log_exception(
            watch.streamer_deps.logger,
            coerced,
            message="Background shell session watch failed before completion.",
            operation=OPERATION_SHELL_BACKGROUND_WATCH,
            details={"session_id": watch.shell_session_id},
        )
        await _finalize_watch(
            watch,
            streamer,
            status=TOOL_CALL_STATUS_ERROR,
            error_message=coerced.message,
            exit_code=None,
            cancellation_safe=False,
        )
        return TOOL_CALL_STATUS_ERROR
    finally:
        await uncancel_then_cleanup(
            _cleanup_watch_session(watch, retain_runtime_session=retain_runtime_session),
        )
