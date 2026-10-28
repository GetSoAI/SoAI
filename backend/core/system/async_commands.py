"""SoAI - Async streaming command executor [backend/core/system/async_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.di.validation import require_dependencies
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.platform.os import is_posix
from core.process.termination import terminate_subprocess_gracefully
from core.system.async_command_streams import (
    close_managed_process_pipes,
    drain_async_command_stream,
)
from core.system.async_process_spawning import (
    ManagedAsyncProcess,
    normalize_async_process_argv,
    spawn_async_process,
    spawn_managed_async_process,
    wait_for_managed_process_group,
)
from core.system.commands import CommandResult
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TokenCollectionProtocol,
)

if TYPE_CHECKING:
    from core.system.process_launcher import ManagedProcess
    from core.types.json import JSONValue

__all__ = (
    "AsyncCommandExecutor",
    "AsyncCommandExecutorDependencies",
)


@dataclass(frozen=True, slots=True)
class AsyncCommandExecutorDependencies:
    executor_logger: LoggerProtocol
    token_collection: TokenCollectionProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AsyncCommandExecutorDependencies",
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            executor_logger=self.executor_logger,
            token_collection=self.token_collection,
        )


class AsyncCommandExecutor:
    __slots__ = (
        "_cancellation_event_bus",
        "_cancellation_history",
        "_token_collection",
        "logger",
    )

    def __init__(self, deps: AsyncCommandExecutorDependencies) -> None:
        self.logger = deps.executor_logger
        self._token_collection = deps.token_collection
        self._cancellation_history = deps.cancellation_history
        self._cancellation_event_bus = deps.cancellation_event_bus

    async def execute(
        self,
        argv: Sequence[str],
        *,
        timeout_sec: float,
        cancellation_id: str,
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
        on_stderr_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> CommandResult:
        operation = "core.system.async_commands.execute"
        argv_list = normalize_async_process_argv(argv)
        owner_value = str(owner or "").strip()
        if not owner_value:
            raise ValidationError("owner is required for async command execution.")
        cancellation_id_value = normalize_cancellation_id(cancellation_id)
        if not cancellation_id_value:
            raise ValidationError("cancellation_id is required for async command execution.")
        timeout_value = max(0.0, float(timeout_sec))
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        process: asyncio.subprocess.Process | ManagedProcess | None = None
        managed: ManagedAsyncProcess | None = None
        async_process: asyncio.subprocess.Process | None = None
        stdout_reader: asyncio.StreamReader | None
        stderr_reader: asyncio.StreamReader | None
        termination: asyncio.Task[None] | None = None
        stdout_task: asyncio.Task[None] | None = None
        stderr_task: asyncio.Task[None] | None = None
        wait_task: asyncio.Task[int] | None = None
        cancel_task: asyncio.Task[None] | None = None

        async def terminate() -> None:
            nonlocal termination
            if process is None or process.returncode is not None:
                return
            if termination is None:

                async def terminate_owned() -> None:
                    if wait_task is not None:
                        await cancel_and_await((wait_task,))
                    if process is not None:
                        try:
                            await terminate_subprocess_gracefully(
                                process,
                                logger=self.logger,
                                operation=operation,
                                process_group=managed is not None,
                            )
                        except ProcessGroupCleanupError as exception:
                            if managed is not None:
                                exception.read_connections = managed.connections
                                exception.stdin_writer = managed.stdin_writer
                            raise

                termination = create_ephemeral_task(
                    terminate_owned(), name="async-command-owned-cleanup", log_exceptions=False
                )
            try:
                await asyncio.shield(termination)
            finally:
                await wait_for_task_completion(termination, retain_resources_until_complete=True)
                termination.result()

        try:
            async with cancellation_token_scope(
                self._token_collection,
                self._cancellation_history,
                self._cancellation_event_bus,
                cancellation_id=cancellation_id_value,
                owner=owner_value,
                metadata=metadata,
                logger=self.logger,
            ) as token:
                if token.thread_event.is_set():
                    return CommandResult(
                        stdout="",
                        return_code=130,
                        stderr=token.cancellation_reason or "Cancelled",
                    )
                try:
                    if is_posix():
                        managed = await spawn_managed_async_process(argv_list)
                        process = managed.process
                        stdout_reader, stderr_reader = managed.stdout_reader, managed.stderr_reader
                        if stdout_reader is None or stderr_reader is None:
                            raise ProcessError(
                                "Managed executor defaults require both output pipes."
                            )
                    else:
                        process = await spawn_async_process(
                            argv_list,
                            stdin=asyncio.subprocess.DEVNULL,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            start_new_session=False,
                        )
                        async_process = process
                        stdout_reader, stderr_reader = process.stdout, process.stderr
                except OSError as exception:
                    return CommandResult(
                        stdout="",
                        return_code=127,
                        stderr=f"Command not found: {exception!s}",
                    )
                read_timeout_sec = 0.5
                stdout_task = create_ephemeral_task(
                    drain_async_command_stream(
                        reader=stdout_reader,
                        chunks=stdout_chunks,
                        on_line=on_stdout_line,
                        stream_name="stdout",
                        process=process,
                        read_timeout_sec=read_timeout_sec,
                        logger=self.logger,
                        operation=operation,
                    ),
                    name=f"async-command-stdout-{cancellation_id_value}",
                )
                stderr_task = create_ephemeral_task(
                    drain_async_command_stream(
                        reader=stderr_reader,
                        chunks=stderr_chunks,
                        on_line=on_stderr_line,
                        stream_name="stderr",
                        process=process,
                        read_timeout_sec=read_timeout_sec,
                        logger=self.logger,
                        operation=operation,
                    ),
                    name=f"async-command-stderr-{cancellation_id_value}",
                )
                if managed is not None:
                    wait_coroutine = wait_for_managed_process_group(managed.process)
                elif async_process is not None:
                    wait_coroutine = async_process.wait()
                else:
                    raise ValidationError("Async command lacks its acquired process authority.")
                wait_task = create_ephemeral_task(
                    wait_coroutine,
                    name=f"async-command-wait-{cancellation_id_value}",
                    log_exceptions=False,
                )
                cancel_task = create_ephemeral_task(
                    token.wait(),
                    name=f"async-command-cancel-{cancellation_id_value}",
                )
                done, _pending = await asyncio.wait(
                    {wait_task, cancel_task},
                    timeout=max(0.0, timeout_value),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                cancelled = (cancel_task in done) and (wait_task not in done)
                timed_out = not done
                if timed_out or cancelled:
                    await terminate()
                if not cancel_task.done():
                    cancel_task.cancel()
                if not timed_out and not cancelled:
                    await wait_task
                await stdout_task
                await stderr_task
                stdout_text = "".join(stdout_chunks)
                stderr_text = "".join(stderr_chunks)
                if timed_out:
                    if not stderr_text:
                        stderr_text = f"Timeout after {timeout_value}s"
                    return CommandResult(stdout=stdout_text, return_code=124, stderr=stderr_text)
                if cancelled:
                    reason_text = token.cancellation_reason or "Cancelled"
                    if not stderr_text:
                        stderr_text = reason_text
                    return CommandResult(stdout=stdout_text, return_code=130, stderr=stderr_text)
                return_code = int(process.returncode or 0)
                return CommandResult(
                    stdout=stdout_text,
                    return_code=return_code,
                    stderr=stderr_text,
                )
        except asyncio.CancelledError:
            await terminate()
            raise
        finally:
            active_exception = sys.exception()
            command_failure = active_exception if isinstance(active_exception, Exception) else None

            async def finalize() -> None:
                try:
                    await terminate()
                finally:
                    await cancel_and_await((cancel_task, stdout_task, stderr_task))
                    await cancel_and_await((wait_task,))
                if managed is not None:
                    await close_managed_process_pipes(
                        managed.process, managed.connections, stdin_writer=managed.stdin_writer
                    )
                failures: list[Exception] = []
                for task in (cancel_task, stdout_task, stderr_task, wait_task):
                    if task is not None and not task.cancelled():
                        failure = task.exception()
                        if isinstance(failure, Exception) and failure is not command_failure:
                            if failure not in failures:
                                failures.append(failure)
                if failures:
                    if command_failure is not None:
                        failures.insert(0, command_failure)
                    raise ExceptionGroup("Async command task cleanup failed.", failures)

            finalization = create_ephemeral_task(
                finalize(), name="async-command-finalization", log_exceptions=False
            )
            try:
                await asyncio.shield(finalization)
            finally:
                await wait_for_task_completion(finalization, retain_resources_until_complete=True)
                finalization.result()
