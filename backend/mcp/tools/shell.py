"""SoAI - MCP utility tool: shell [backend/mcp/tools/shell.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import shlex
import uuid
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.terminal.command_truncation import truncate_shell_command
from core.terminal.requests import CreatePTYSessionRequest
from mcp.tools.access_control import require_tool_action
from mcp.tools.error import MCPToolError
from mcp.tools.files_access import resolve_existing_dir
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.shell_deferral import maybe_defer_background_shell
from mcp.tools.shell_foreground_completion import finish_foreground_shell
from mcp.tools.shell_parsing import parse_shell_tool_request
from mcp.tools.shell_policy import enforce_shell_policy
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    close_shell_session_resources,
)
from mcp.tools.shell_session_output_streaming import publish_shell_session_output_delta
from mcp.tools.shell_session_support import (
    build_interactive_shell,
    build_non_tty_shell_command,
    cleanup_pruned_shell_sessions,
    load_shell_blacklist,
    resolve_requested_workdir,
)
from mcp.tools.shell_stream_handoff import complete_or_defer_streamed_shell
from mcp.tools.shell_transcript_paths import resolve_shell_transcript_root

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_shell",)

LOGGER_NAME_MCP_TOOLS_SHELL = "SoAI.mcp.tools.shell"
OPERATION_MCP_TOOLS_SHELL = "mcp.tools.shell_session_tools.tool_shell"
OPERATION_MCP_TOOLS_SHELL_CLEANUP = "mcp.tools.shell_session_tools.tool_shell.cleanup"
OPERATION_MCP_TOOLS_SHELL_CLEANUP_CANCELLED = (
    "mcp.tools.shell_session_tools.tool_shell.cleanup_cancelled"
)
OPERATION_MCP_TOOLS_SHELL_EXIT_CLEANUP = "mcp.tools.shell_session_tools.tool_shell.exit_cleanup"


async def tool_shell(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    await require_tool_action(
        utility_tools,
        action=AccessAction.TERMINAL_USE,
        tool_name="shell",
    )
    parsed = parse_shell_tool_request(dict(arguments))
    cmd = parsed.cmd
    login = parsed.login
    tty = parsed.tty
    run_in_background = parsed.run_in_background
    stream_output = parsed.stream_output
    yield_time_ms = parsed.yield_time_ms
    resolved_cols = parsed.cols
    resolved_rows = parsed.rows
    shell_exe = parsed.shell_exe
    max_output_chars = parsed.max_output_chars
    output_limit = parsed.output_limit
    logger = get_logger(LOGGER_NAME_MCP_TOOLS_SHELL)
    cleanup_deps = ShellSessionCleanupDeps(
        runtime_sessions=utility_tools.runtime_sessions,
        terminal=utility_tools.terminal,
        logger=logger,
    )

    blacklist = load_shell_blacklist(utility_tools)
    enforce_shell_policy(cmd, blacklist=blacklist, tool_name="shell")

    await cleanup_pruned_shell_sessions(
        utility_tools,
        logger=logger,
        operation="mcp.tools.shell_session_tools.tool_shell.pruned_cleanup",
    )

    if not utility_tools.config.get_bool("TOOLS.MCP.SHELL.ENABLED"):
        raise MCPToolError(
            -32603,
            "shell is disabled by configuration (TOOLS.MCP.SHELL.ENABLED=false). Set TOOLS.MCP.SHELL.ENABLED=true in config.yaml to enable it.",
        )

    owner_key = utility_tools.runtime_sessions.current_owner_key()
    workspace_path = utility_tools.runtime_sessions.require_workspace_path(owner_key)
    tool_call_identity = utility_tools.active_tool_call_context.get(None)
    resolved_workdir = workspace_path
    requested_workdir = resolve_requested_workdir(arguments)
    if isinstance(requested_workdir, str) and requested_workdir.strip():
        resolved_workdir = resolve_existing_dir(
            utility_tools,
            requested_workdir,
            description="workdir",
        )

    terminal_session_id = f"mcp_shell_{uuid.uuid4().hex[:16]}"
    shell_session = utility_tools.runtime_sessions.create_shell_session(
        terminal_session_id,
        owner_key,
    )
    try:
        transcript_root = resolve_shell_transcript_root(utility_tools.config)
        utility_tools.runtime_sessions.create_shell_transcript(
            shell_session.session_id,
            transcript_root,
        )
    except HANDLED_RUNTIME_EXCEPTIONS:
        utility_tools.runtime_sessions.close_shell_session(shell_session.session_id)
        raise
    shell_session.run_in_background = run_in_background
    await cleanup_pruned_shell_sessions(
        utility_tools,
        logger=logger,
        operation="mcp.tools.shell_session_tools.tool_shell.pruned_cleanup",
    )

    def _on_output(data: bytes) -> None:
        session = utility_tools.runtime_sessions.get_shell_session(shell_session.session_id)
        if session is None:
            return
        utility_tools.runtime_sessions.append_shell_output(shell_session.session_id, data)
        if run_in_background or session.run_in_background or session.background_watch_started:
            publish_shell_session_output_delta(
                event_bus=utility_tools.event_bus,
                identity=tool_call_identity,
                tool_name="shell",
                delta=data.decode("utf-8", errors="replace"),
            )

    def _on_exit(_session_id: str, exit_code: int) -> None:
        utility_tools.runtime_sessions.mark_shell_exit(shell_session.session_id, exit_code)

    terminal_created = False
    try:
        if tty and not stream_output:
            interactive_shell = build_interactive_shell(shell_exe=shell_exe, login=login)
            request = CreatePTYSessionRequest(
                session_id=terminal_session_id,
                cols=resolved_cols,
                rows=resolved_rows,
                user_id=utility_tools.runtime_sessions.current_user_id(),
                shell=interactive_shell,
                output_callback=_on_output,
                exit_callback=_on_exit,
            )
            await utility_tools.terminal.create_pty_session(request)
            terminal_created = True
            await utility_tools.terminal.write_pty_input(
                terminal_session_id,
                f"cd {shlex.quote(resolved_workdir)}\n".encode("utf-8", errors="replace"),
            )
            await utility_tools.terminal.write_pty_input(
                terminal_session_id,
                f"{cmd.rstrip('\n')}\n".encode("utf-8", errors="replace"),
            )
        else:
            request = CreatePTYSessionRequest(
                session_id=terminal_session_id,
                cols=resolved_cols,
                rows=resolved_rows,
                user_id=utility_tools.runtime_sessions.current_user_id(),
                shell=build_non_tty_shell_command(
                    shell_exe=shell_exe,
                    login=login,
                    workdir=resolved_workdir,
                    cmd=cmd,
                ),
                output_callback=_on_output,
                exit_callback=_on_exit,
            )
            await utility_tools.terminal.create_pty_session(request)
            terminal_created = True
    except asyncio.CancelledError:
        if terminal_created:
            await uncancel_then_cleanup(
                close_shell_session_resources(
                    cleanup_deps,
                    operation=OPERATION_MCP_TOOLS_SHELL_CLEANUP_CANCELLED,
                    shell_session_id=shell_session.session_id,
                    terminal_session_id=terminal_session_id,
                ),
            )
        else:
            utility_tools.runtime_sessions.close_shell_session(shell_session.session_id)
        logger.debug("PTY session setup cancelled.")
        raise
    except RECOVERABLE_EXCEPTIONS as setup_error:
        coerced = coerce_to_soai_error(
            setup_error,
            operation=OPERATION_MCP_TOOLS_SHELL,
        )
        log_exception(
            logger,
            coerced,
            message="PTY session setup failed.",
            operation=OPERATION_MCP_TOOLS_SHELL,
            details={"cmd": truncate_shell_command(cmd)},
        )
        if terminal_created:
            await close_shell_session_resources(
                cleanup_deps,
                operation=OPERATION_MCP_TOOLS_SHELL_CLEANUP,
                shell_session_id=shell_session.session_id,
                terminal_session_id=terminal_session_id,
            )
        else:
            utility_tools.runtime_sessions.close_shell_session(shell_session.session_id)
        raise

    if stream_output:
        return await complete_or_defer_streamed_shell(
            utility_tools=utility_tools,
            logger=logger,
            tty=tty,
            shell_session_id=shell_session.session_id,
            terminal_session_id=terminal_session_id,
            max_output_chars=max_output_chars,
            output_limit=output_limit,
            yield_time_ms=yield_time_ms,
        )

    try:
        deferred_result = await maybe_defer_background_shell(
            utility_tools,
            tty=tty,
            run_in_background=run_in_background,
            shell_session_id=shell_session.session_id,
            terminal_session_id=terminal_session_id,
            max_output_chars=max_output_chars,
            output_limit=output_limit,
            accepted_result={
                "session_id": int(shell_session.session_id),
                "status": "running",
            },
        )
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            close_shell_session_resources(
                cleanup_deps,
                operation=OPERATION_MCP_TOOLS_SHELL_CLEANUP_CANCELLED,
                shell_session_id=shell_session.session_id,
                terminal_session_id=terminal_session_id,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await close_shell_session_resources(
            cleanup_deps,
            operation=OPERATION_MCP_TOOLS_SHELL_CLEANUP,
            shell_session_id=shell_session.session_id,
            terminal_session_id=terminal_session_id,
        )
        raise
    if deferred_result is not None:
        return deferred_result

    return await finish_foreground_shell(
        utility_tools=utility_tools,
        cleanup_deps=cleanup_deps,
        shell_session=shell_session,
        terminal_session_id=terminal_session_id,
        tty=tty,
        yield_time_ms=yield_time_ms,
        output_limit=output_limit,
        operation=OPERATION_MCP_TOOLS_SHELL_EXIT_CLEANUP,
    )
