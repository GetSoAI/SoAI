"""SoAI - Async streaming command executor [backend/core/system/async_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.platform.os import is_posix
from core.process.termination import terminate_subprocess_gracefully
from core.system.async_command_streams import drain_async_command_stream
from core.system.async_process_spawning import (
    normalize_async_process_argv,
    spawn_async_process,
)
from core.system.commands import CommandResult
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TokenCollectionProtocol,
)
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC

if TYPE_CHECKING:
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
        process: asyncio.subprocess.Process | None = None
        stdout_task: asyncio.Task[None] | None = None
        stderr_task: asyncio.Task[None] | None = None
        wait_task: asyncio.Task[int] | None = None
        cancel_task: asyncio.Task[None] | None = None
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
                    process = await spawn_async_process(
                        argv_list,
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=is_posix(),
                    )
                except OSError as exception:
                    return CommandResult(
                        stdout="",
                        return_code=127,
                        stderr=f"Command not found: {exception!s}",
                    )
                read_timeout_sec = 0.5
                stdout_task = create_ephemeral_task(
                    drain_async_command_stream(
                        reader=process.stdout,
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
                        reader=process.stderr,
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
                wait_task = create_ephemeral_task(
                    process.wait(),
                    name=f"async-command-wait-{cancellation_id_value}",
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
                    await _terminate_process(
                        process,
                        logger=self.logger,
                        operation=operation,
                    )
                if wait_task not in done:
                    _done_wait, pending_wait = await asyncio.wait(
                        {wait_task},
                        timeout=RESPONSIVE_TIMEOUT_SEC,
                    )
                    if pending_wait:
                        await _terminate_process(process, logger=self.logger, operation=operation)
                        await asyncio.wait(
                            {wait_task},
                            timeout=RESPONSIVE_TIMEOUT_SEC,
                        )
                if not cancel_task.done():
                    cancel_task.cancel()
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
            if process is not None:
                await _terminate_process(process, logger=self.logger, operation=operation)
            raise
        finally:
            if cancel_task and (not cancel_task.done()):
                cancel_task.cancel()
            await _finalize_task(stdout_task)
            await _finalize_task(stderr_task)
            await _finalize_task(wait_task)
            if process is not None and process.returncode is None:
                await _terminate_process(process, logger=self.logger, operation=operation)


async def _terminate_process(
    process: asyncio.subprocess.Process,
    *,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    if process.returncode is not None:
        return
    await terminate_subprocess_gracefully(
        process,
        logger=logger,
        operation=operation,
        process_group=is_posix(),
    )


async def _finalize_task[T](task: asyncio.Task[T] | None) -> None:
    await cancel_and_await_task(task)
