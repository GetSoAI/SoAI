"""SoAI - Plugin SDK managed process sessions [backend/plugin_sdk/contracts/process_sessions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import logging
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

import psutil

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.platform.os import is_windows
from core.system.async_process_spawning import spawn_async_process
from plugin_sdk.contracts.process_lifecycle import (
    check_process_alive,
    terminate_managed_process,
)
from plugin_sdk.contracts.process_streams import consume_process_stream

__all__ = (
    "ManagedProcessSession",
    "spawn_logged_process",
    "terminate_logged_process",
)

OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_SESSIONS_SPAWN_LOGGED_PROCESS = (
    "plugin_sdk.contracts.process_sessions.spawn_logged_process"
)
PROCESS_SESSION_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


@dataclass(slots=True)
class ManagedProcessSession:
    process: asyncio.subprocess.Process
    process_group_id: int | None = None
    log_consumer_tasks: list[asyncio.Task[None]] = field(default_factory=list)
    log_file_handle: io.BufferedIOBase | None = None

    def active_pids(self) -> list[int]:
        if self.process_group_id is not None and not is_windows():
            return _active_process_group_pids(self.process_group_id)
        if check_process_alive(self.process):
            return [int(self.process.pid)]
        return []


def _active_process_group_pids(process_group_id: int) -> list[int]:
    active_pids: list[int] = []
    try:
        pids = psutil.pids()
    except psutil.Error:
        return active_pids
    for pid in pids:
        try:
            if os.getpgid(pid) == process_group_id:
                active_pids.append(pid)
        except OSError:
            continue
    return sorted(active_pids)


async def spawn_logged_process(
    argv: Sequence[str],
    *,
    cwd: str | None,
    env: Mapping[str, str] | None,
    logger: logging.Logger,
    plugin_label: str,
    log_file_handle: io.BufferedIOBase | None,
    stdin: int | None = None,
    stdout: int | None = asyncio.subprocess.PIPE,
    stderr: int | None = asyncio.subprocess.PIPE,
    start_new_session: bool = False,
    creationflags: int = 0,
    strip_ansi: bool = False,
) -> ManagedProcessSession:
    spawn_task = create_ephemeral_task(
        spawn_async_process(
            argv,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
            cwd=cwd,
            start_new_session=start_new_session,
            creationflags=creationflags,
        ),
        name=f"{plugin_label}-process-spawn",
        log_exceptions=False,
    )
    process: asyncio.subprocess.Process | None
    try:
        process = await asyncio.shield(spawn_task)
    except asyncio.CancelledError:
        process = await _collect_spawned_process_after_cancellation(
            spawn_task=spawn_task,
            logger=logger,
            plugin_label=plugin_label,
        )
        if process is not None:
            await _terminate_spawn_failure_session(
                session=_build_process_session(
                    process=process,
                    log_file_handle=log_file_handle,
                    start_new_session=start_new_session,
                ),
                logger=logger,
                plugin_label=plugin_label,
                use_process_group=start_new_session or creationflags != 0,
            )
        else:
            await _close_spawn_failure_log_handle(
                log_file_handle=log_file_handle,
                logger=logger,
                plugin_label=plugin_label,
            )
        raise
    except PROCESS_SESSION_OPERATION_EXCEPTIONS:
        await _close_spawn_failure_log_handle(
            log_file_handle=log_file_handle,
            logger=logger,
            plugin_label=plugin_label,
        )
        raise
    if process is None:
        raise StateError("Process spawn completed without a process instance.")
    session = _build_process_session(
        process=process,
        log_file_handle=log_file_handle,
        start_new_session=start_new_session,
    )
    try:
        if process.stdout is not None:
            session.log_consumer_tasks.append(
                create_ephemeral_task(
                    consume_process_stream(
                        process.stdout,
                        logger=logger,
                        log_file_handle=log_file_handle,
                        plugin_label=plugin_label,
                        strip_ansi=strip_ansi,
                    ),
                    name=f"{plugin_label}-stdout-consumer",
                ),
            )
        if process.stderr is not None:
            session.log_consumer_tasks.append(
                create_ephemeral_task(
                    consume_process_stream(
                        process.stderr,
                        logger=logger,
                        log_file_handle=log_file_handle,
                        plugin_label=plugin_label,
                        strip_ansi=strip_ansi,
                    ),
                    name=f"{plugin_label}-stderr-consumer",
                ),
            )
    except asyncio.CancelledError:
        await _terminate_spawn_failure_session(
            session=session,
            logger=logger,
            plugin_label=plugin_label,
            use_process_group=start_new_session or creationflags != 0,
        )
        raise
    except PROCESS_SESSION_OPERATION_EXCEPTIONS:
        await _terminate_spawn_failure_session(
            session=session,
            logger=logger,
            plugin_label=plugin_label,
            use_process_group=start_new_session or creationflags != 0,
        )
        raise
    return session


async def terminate_logged_process(
    session: ManagedProcessSession,
    *,
    logger: logging.Logger,
    plugin_label: str,
    shutdown_timeout_sec: float = 30.0,
    kill_wait_sec: float = 10.0,
    use_process_group: bool = True,
    force_kill_tree_callback: Callable[[int, float], Awaitable[bool]] | None = None,
) -> bool:
    return await terminate_managed_process(
        process=session.process,
        process_group_id=session.process_group_id,
        logger=logger,
        plugin_label=plugin_label,
        shutdown_timeout_sec=shutdown_timeout_sec,
        kill_wait_sec=kill_wait_sec,
        use_process_group=use_process_group,
        force_kill_tree_callback=force_kill_tree_callback,
        log_consumer_tasks=session.log_consumer_tasks,
        log_file_handle=session.log_file_handle,
    )


async def _terminate_spawn_failure_session(
    *,
    session: ManagedProcessSession,
    logger: logging.Logger,
    plugin_label: str,
    use_process_group: bool,
) -> None:
    await terminate_managed_process(
        process=session.process,
        process_group_id=session.process_group_id,
        logger=logger,
        plugin_label=plugin_label,
        shutdown_timeout_sec=0.0,
        kill_wait_sec=5.0,
        use_process_group=use_process_group,
        log_consumer_tasks=session.log_consumer_tasks,
        log_file_handle=session.log_file_handle,
    )


def _build_process_session(
    *,
    process: asyncio.subprocess.Process,
    log_file_handle: io.BufferedIOBase | None,
    start_new_session: bool,
) -> ManagedProcessSession:
    process_group_id = int(process.pid) if start_new_session and not is_windows() else None
    return ManagedProcessSession(
        process=process,
        process_group_id=process_group_id,
        log_file_handle=log_file_handle,
    )


async def _collect_spawned_process_after_cancellation(
    *,
    spawn_task: asyncio.Task[asyncio.subprocess.Process],
    logger: logging.Logger,
    plugin_label: str,
) -> asyncio.subprocess.Process | None:
    try:
        return await uncancel_and_wait(spawn_task)
    except asyncio.CancelledError:
        return None
    except PROCESS_SESSION_OPERATION_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=f"{plugin_label}.start.spawn",
        )
        log_exception(
            logger,
            coerced,
            message="Process spawn failed while handling startup cancellation",
            operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_SESSIONS_SPAWN_LOGGED_PROCESS,
        )
        return None


async def _close_spawn_failure_log_handle(
    *,
    log_file_handle: io.BufferedIOBase | None,
    logger: logging.Logger,
    plugin_label: str,
) -> None:
    if log_file_handle is None:
        return
    try:
        await uncancel_and_wait(asyncio.to_thread(log_file_handle.close))
    except OSError as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=f"{plugin_label}.start.close_log",
        )
        log_exception(
            logger,
            coerced,
            message="Failed to close process log file after spawn failure",
            operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_SESSIONS_SPAWN_LOGGED_PROCESS,
        )
