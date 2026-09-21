"""SoAI - Async subprocess spawning and lifecycle primitives [backend/core/system/async_process_spawning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
from collections.abc import Mapping, Sequence

from core.errors.exceptions import ValidationError
from core.system.subprocess_platform import resolve_subprocess_creationflags
from core.timing.constants import EXTENDED_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC

__all__ = (
    "normalize_async_process_argv",
    "spawn_async_process",
    "terminate_async_process_nowait",
    "wait_for_async_process_exit",
)


def normalize_async_process_argv(argv: Sequence[str]) -> list[str]:
    argv_list = [str(part) for part in argv]
    if not argv_list:
        raise ValidationError("argv must contain at least one element.")
    return argv_list


def _resolve_subprocess_stream_target(
    target: int | io.BufferedIOBase | io.RawIOBase | None,
) -> int | None:
    if target is None or isinstance(target, int):
        return target
    return target.fileno()


async def spawn_async_process(
    argv: Sequence[str],
    *,
    stdin: int | None,
    stdout: int | io.BufferedIOBase | io.RawIOBase | None,
    stderr: int | io.BufferedIOBase | io.RawIOBase | None,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    start_new_session: bool = False,
    creationflags: int = 0,
    limit: int = 65_536,
) -> asyncio.subprocess.Process:
    argv_list = normalize_async_process_argv(argv)
    return await asyncio.create_subprocess_exec(
        *argv_list,
        stdin=stdin,
        stdout=_resolve_subprocess_stream_target(stdout),
        stderr=_resolve_subprocess_stream_target(stderr),
        env=dict(env) if env is not None else None,
        cwd=cwd,
        start_new_session=start_new_session,
        creationflags=resolve_subprocess_creationflags(creationflags),
        limit=limit,
    )


def terminate_async_process_nowait(process: asyncio.subprocess.Process) -> bool:
    if process.returncode is not None:
        return False
    try:
        process.terminate()
    except ProcessLookupError:
        return False
    return True


async def wait_for_async_process_exit(
    process: asyncio.subprocess.Process,
    *,
    timeout_sec: float = EXTENDED_TIMEOUT_SEC,
    kill_on_timeout: bool = False,
) -> None:
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout_sec)
    except TimeoutError:
        if not kill_on_timeout:
            raise
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
                return
        await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
