"""SoAI - MCP ripgrep subprocess lifecycle helpers for grep_files [backend/mcp/tools/grep_ripgrep_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.system.async_process_spawning import (
    spawn_async_process,
    terminate_async_process_nowait,
    wait_for_async_process_exit,
)
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from mcp.tools.error import MCPToolError

__all__ = (
    "drain_process_uninterruptible",
    "raise_for_returncode",
    "read_stderr",
    "spawn_ripgrep_process",
    "terminate_process",
)


async def spawn_ripgrep_process(
    args: list[str],
) -> tuple[asyncio.subprocess.Process, asyncio.StreamReader]:
    proc = await spawn_async_process(
        args,
        stdin=None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout = proc.stdout
    if stdout is None:
        try:
            proc.kill()
        except ProcessLookupError as exception:
            await wait_for_async_process_exit(
                proc,
                timeout_sec=RESPONSIVE_TIMEOUT_SEC,
                kill_on_timeout=True,
            )
            raise MCPToolError(-32603, "Ripgrep did not produce stdout.") from exception
        await wait_for_async_process_exit(
            proc,
            timeout_sec=RESPONSIVE_TIMEOUT_SEC,
            kill_on_timeout=True,
        )
        raise MCPToolError(-32603, "Ripgrep did not produce stdout.")
    return proc, stdout


def terminate_process(proc: asyncio.subprocess.Process) -> None:
    terminate_async_process_nowait(proc)


async def drain_process(proc: asyncio.subprocess.Process, *, terminated: bool) -> None:
    if terminated:
        await wait_for_async_process_exit(
            proc,
            timeout_sec=RESPONSIVE_TIMEOUT_SEC,
            kill_on_timeout=True,
        )
        return
    await wait_for_async_process_exit(proc)


async def drain_process_uninterruptible(
    proc: asyncio.subprocess.Process,
    *,
    terminated: bool,
) -> None:
    task = asyncio.current_task()
    cancel_exception: asyncio.CancelledError | None = None
    cancelled_requests_total = 0
    terminated_flag = terminated
    drain_completed = False
    while not drain_completed:
        try:
            await drain_process(proc, terminated=terminated_flag)
            drain_completed = True
        except asyncio.CancelledError as exception:
            cancel_exception = exception
            if task is None:
                raise
            cancel_requests = task.cancelling()
            cancelled_requests_total += cancel_requests
            while cancel_requests > 0:
                task.uncancel()
                cancel_requests -= 1
            terminate_process(proc)
            terminated_flag = True
    if cancel_exception is not None and task is not None:
        while cancelled_requests_total > 0:
            task.cancel()
            cancelled_requests_total -= 1
        raise cancel_exception


def format_stderr_for_error(stderr_text: str) -> str:
    flattened = " ".join(line.strip() for line in stderr_text.splitlines() if line.strip())
    if not flattened:
        return ""
    if len(flattened) <= 400:
        return flattened
    return f"{flattened[:397]}..."


async def read_stderr(proc: asyncio.subprocess.Process) -> str:
    stderr = proc.stderr
    if stderr is None:
        return ""
    try:
        data = await asyncio.wait_for(stderr.read(8192), timeout=RESPONSIVE_TIMEOUT_SEC)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def raise_for_returncode(
    proc: asyncio.subprocess.Process,
    *,
    truncated: bool,
    stderr_text: str,
) -> None:
    if truncated:
        return
    if proc.returncode in (0, 1):
        return
    stderr_formatted = format_stderr_for_error(stderr_text)
    if proc.returncode == 2:
        suffix = f": {stderr_formatted}" if stderr_formatted else ""
        if "regex parse error" in stderr_text.lower():
            raise MCPToolError(-32602, f"Invalid regex pattern{suffix}")
        raise MCPToolError(-32602, f"Ripgrep error{suffix}")
    suffix = f" {stderr_formatted}" if stderr_formatted else ""
    raise MCPToolError(-32603, f"Ripgrep exited with non-zero status {proc.returncode}.{suffix}")
