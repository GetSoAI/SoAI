"""SoAI - Managed IPC worker process spawning [backend/core/ipc/managed_worker_spawn.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from core.filesystem.open_files import open_binary
from core.system.async_process_spawning import spawn_async_process
from core.system.subprocess_platform import windows_isolated_process_creationflags

__all__ = ("spawn_managed_ipc_process",)


async def spawn_managed_ipc_process(
    argv: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    diagnostic_log_path: str,
    start_new_session: bool,
) -> asyncio.subprocess.Process:
    resolved_log_path = diagnostic_log_path.strip()
    if not resolved_log_path:
        return await spawn_async_process(
            argv,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=start_new_session,
            creationflags=windows_isolated_process_creationflags(),
        )
    log_dir = os.path.dirname(os.path.abspath(resolved_log_path))
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    with open_binary(resolved_log_path, mode="ab") as diagnostic_stream:
        return await spawn_async_process(
            argv,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=diagnostic_stream,
            stderr=diagnostic_stream,
            start_new_session=start_new_session,
            creationflags=windows_isolated_process_creationflags(),
        )
