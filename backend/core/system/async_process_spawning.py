"""SoAI - Async subprocess spawning and lifecycle primitives [backend/core/system/async_process_spawning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import (
    run_idempotent_current_task_operation,
    wait_for_task_completion,
)
from core.concurrency.deadlines import deadline_after
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.platform.os import is_posix
from core.process.termination import (
    confirm_owned_process_group_exit,
    terminate_subprocess_gracefully,
)
from core.system.async_command_streams import (
    ManagedAsyncPipes,
    close_managed_process_pipes,
    connect_managed_process_pipes,
)
from core.system.process_launcher import spawn_managed_process
from core.system.subprocess_platform import (
    resolve_subprocess_creationflags,
    resolve_subprocess_environment,
    resolve_subprocess_paths,
)
from core.timing.constants import EXTENDED_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC, MODERATE_DELAY_SEC
from core.validation.strict_numbers import require_positive_int_strict

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.system.process_launcher import ManagedProcess


__all__ = (
    "ManagedAsyncProcess",
    "retain_managed_process_cleanup",
    "wait_for_managed_process_group",
    "spawn_managed_async_process",
    "normalize_async_process_argv",
    "spawn_async_process",
    "terminate_async_process_nowait",
    "wait_for_async_process_exit",
)


LOGGER_NAME = "SoAI.core.system.async_process_spawning"


@dataclass(frozen=True, slots=True)
class ManagedAsyncProcess:
    process: ManagedProcess
    stdout_reader: asyncio.StreamReader | None
    stderr_reader: asyncio.StreamReader | None
    connections: tuple[tuple[asyncio.ReadTransport, asyncio.StreamReader], ...]
    stdin_writer: asyncio.StreamWriter | None = None


def retain_managed_process_cleanup(error: ProcessGroupCleanupError) -> ManagedAsyncProcess:
    return ManagedAsyncProcess(
        error.process, None, None, error.read_connections, error.stdin_writer
    )


async def wait_for_managed_process_group(
    process: ManagedProcess,
    *,
    timeout_sec: float | None = None,
    pool: BoundedBlockingPool | None = None,
) -> int:
    deadline = None if timeout_sec is None else deadline_after(timeout_sec)

    def observe_exit() -> bool:
        return confirm_owned_process_group_exit(
            process,
            timeout_sec=(
                LOCAL_IO_TIMEOUT_SEC
                if deadline is None
                else min(LOCAL_IO_TIMEOUT_SEC, deadline.remaining_seconds())
            ),
        )

    while True:
        if deadline is not None and deadline.expired():
            raise TimeoutError("Owned process group did not exit before its deadline.")
        if await run_joined_thread_call(
            observe_exit,
            task_name="core.system.managed-process-group-observation",
            retain_resources_until_complete=True,
            pool=pool,
            admission_deadline=deadline,
        ):
            if process.returncode is None:
                raise ProcessError("Verified process-group exit lacks its child result.")
            return process.returncode
        await asyncio.sleep(
            MODERATE_DELAY_SEC
            if deadline is None
            else min(MODERATE_DELAY_SEC, deadline.remaining_seconds())
        )


async def spawn_managed_async_process(
    argv: Sequence[str],
    *,
    stdin: int | io.BufferedIOBase | io.RawIOBase | None = asyncio.subprocess.DEVNULL,
    stdout: int | io.BufferedIOBase | io.RawIOBase | None = asyncio.subprocess.PIPE,
    stderr: int | io.BufferedIOBase | io.RawIOBase | None = asyncio.subprocess.PIPE,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    creationflags: int = 0,
    limit: int = 65_536,
) -> ManagedAsyncProcess:
    if not is_posix():
        raise ProcessError("Managed async process groups require POSIX child ownership.")
    argv_list = normalize_async_process_argv(argv)
    require_positive_int_strict(limit, error_message="Managed pipe limit must be positive.")
    input_target, output_target, error_target = (
        _resolve_subprocess_stream_target(target) for target in (stdin, stdout, stderr)
    )

    completed = Event()
    dispatched = False
    created_process: ManagedProcess | None = None

    def create_process() -> ManagedProcess:
        nonlocal created_process
        try:
            spawned_process = spawn_managed_process(
                argv_list,
                stdin=input_target,
                stdout=output_target,
                stderr=error_target,
                env=env,
                cwd=cwd,
                creationflags=creationflags,
                start_new_session=True,
                text=False,
                bufsize=0,
            )
            created_process = spawned_process
            return spawned_process
        finally:
            completed.set()

    async def dispatch_creation() -> ManagedProcess:
        nonlocal dispatched
        dispatched = True
        return await asyncio.to_thread(create_process)

    creation = create_ephemeral_task(
        dispatch_creation(),
        name="core.system.managed-process-spawn",
        log_exceptions=False,
    )
    process: ManagedProcess | None = None
    pipes = ManagedAsyncPipes()
    try:
        acquired_process = await asyncio.shield(creation)
        process = acquired_process
        await connect_managed_process_pipes(acquired_process, pipes, limit=limit)
        return ManagedAsyncProcess(
            acquired_process,
            pipes.stdout_reader,
            pipes.stderr_reader,
            tuple(pipes.connections),
            pipes.stdin_writer,
        )
    except asyncio.CancelledError as exception:
        acquisition_failure: BaseException = exception
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        acquisition_failure = exception
    try:
        raise acquisition_failure
    finally:
        await wait_for_task_completion(creation, retain_resources_until_complete=True)
        if dispatched:

            async def join_creation() -> None:
                await run_joined_thread_call(
                    completed.wait,
                    task_name="core.system.managed-process-spawn-completion",
                    retain_resources_until_complete=True,
                )

            await run_idempotent_current_task_operation(
                join_creation, restore_cancellation_requests=False
            )
            process = created_process
        if process is not None:
            owned_process = process

            async def cleanup_acquisition() -> None:
                try:
                    await terminate_subprocess_gracefully(
                        owned_process,
                        logger=get_logger(LOGGER_NAME),
                        operation="core.system.async_process_spawning.cleanup",
                        process_group=True,
                    )
                except ProcessGroupCleanupError as exception:
                    exception.read_connections = tuple(pipes.connections)
                    exception.stdin_writer = pipes.stdin_writer
                    raise
                await close_managed_process_pipes(
                    owned_process, tuple(pipes.connections), stdin_writer=pipes.stdin_writer
                )

            cleanup = create_ephemeral_task(
                cleanup_acquisition(),
                name="core.system.managed-process-acquisition-cleanup",
                log_exceptions=False,
            )
            try:
                await asyncio.shield(cleanup)
            finally:
                await wait_for_task_completion(cleanup, retain_resources_until_complete=True)
                cleanup.result()


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
    process_paths = await run_joined_thread_call(
        resolve_subprocess_paths,
        argv_list,
        cwd,
        task_name="core.system.async_process_spawning.paths",
        retain_resources_until_complete=True,
    )
    process_environment = await run_joined_thread_call(
        resolve_subprocess_environment,
        env,
        task_name="core.system.async_process_spawning.environment",
        retain_resources_until_complete=True,
    )
    return await asyncio.create_subprocess_exec(
        *argv_list,
        executable=process_paths.executable,
        stdin=stdin,
        stdout=_resolve_subprocess_stream_target(stdout),
        stderr=_resolve_subprocess_stream_target(stderr),
        env=process_environment,
        cwd=process_paths.working_directory,
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
