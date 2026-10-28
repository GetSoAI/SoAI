"""SoAI - Async command output stream draining [backend/core/system/async_command_streams.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "drain_async_command_stream",
    "ManagedAsyncPipes",
    "connect_managed_process_pipes",
    "close_managed_process_pipes",
)


async def drain_async_command_stream(
    reader: asyncio.StreamReader | None,
    *,
    chunks: list[str],
    on_line: Callable[[str], Awaitable[None]] | None,
    stream_name: str,
    process: asyncio.subprocess.Process | ManagedProcess,
    read_timeout_sec: float,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    if reader is None:
        return
    timeout_value = max(0.05, float(read_timeout_sec))
    post_exit_timeouts = 0
    max_post_exit_timeouts = 6
    while True:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=timeout_value)
        except TimeoutError:
            if process.returncode is not None:
                post_exit_timeouts += 1
                if post_exit_timeouts >= max_post_exit_timeouts:
                    break
            else:
                post_exit_timeouts = 0
            continue
        post_exit_timeouts = 0
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        chunks.append(decoded)
        if on_line is not None:
            try:
                await on_line(decoded.rstrip("\r\n"))
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Async command output callback failed.",
                    operation=operation,
                    details={"stream": stream_name},
                    level="warning",
                )
                raise


@dataclass(slots=True)
class ManagedAsyncPipes:
    stdout_reader: asyncio.StreamReader | None = None
    stderr_reader: asyncio.StreamReader | None = None
    stdin_writer: asyncio.StreamWriter | None = None
    connections: list[tuple[asyncio.ReadTransport, asyncio.StreamReader]] = field(
        default_factory=list[tuple[asyncio.ReadTransport, asyncio.StreamReader]]
    )


async def _connect_owned_pipe[PipeTransport: asyncio.BaseTransport](
    connection: Coroutine[None, None, tuple[PipeTransport, asyncio.StreamReaderProtocol]],
    on_connected: Callable[[PipeTransport, asyncio.StreamReaderProtocol], None],
) -> None:
    task = create_ephemeral_task(
        connection, name="core.system.managed-process-pipe", log_exceptions=False
    )
    try:
        await asyncio.shield(task)
    finally:
        await wait_for_task_completion(task, retain_resources_until_complete=True)
        if not task.cancelled() and task.exception() is None:
            on_connected(*task.result())


async def connect_managed_process_pipes(
    process: ManagedProcess, pipes: ManagedAsyncPipes, *, limit: int
) -> None:
    loop = asyncio.get_running_loop()
    if process.stdin is not None:
        if not isinstance(process.stdin, io.RawIOBase):
            raise ProcessError("Managed stdin requires owned unbuffered binary bytes.")
        input_reader = asyncio.StreamReader(limit=limit)
        input_protocol = asyncio.StreamReaderProtocol(input_reader)

        def accept_input(
            transport: asyncio.WriteTransport, protocol: asyncio.StreamReaderProtocol
        ) -> None:
            pipes.stdin_writer = asyncio.StreamWriter(transport, protocol, input_reader, loop)

        await _connect_owned_pipe(
            loop.connect_write_pipe(lambda: input_protocol, process.stdin), accept_input
        )
    for stream_name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
        if pipe is None:
            continue
        if not isinstance(pipe, io.RawIOBase):
            raise ProcessError("Managed output requires owned unbuffered binary bytes.")
        reader = asyncio.StreamReader(limit=limit)
        protocol = asyncio.StreamReaderProtocol(reader)

        def accept_output(
            transport: asyncio.ReadTransport,
            _connected_protocol: asyncio.StreamReaderProtocol,
            *,
            selected_stream: str = stream_name,
            selected_reader: asyncio.StreamReader = reader,
        ) -> None:
            pipes.connections.append((transport, selected_reader))
            if selected_stream == "stdout":
                pipes.stdout_reader = selected_reader
            else:
                pipes.stderr_reader = selected_reader

        def create_output_protocol(
            selected_protocol: asyncio.StreamReaderProtocol = protocol,
        ) -> asyncio.StreamReaderProtocol:
            return selected_protocol

        await _connect_owned_pipe(
            loop.connect_read_pipe(create_output_protocol, pipe), accept_output
        )


async def close_managed_process_pipes(
    process: ManagedProcess,
    connections: tuple[tuple[asyncio.ReadTransport, asyncio.StreamReader], ...],
    *,
    stdin_writer: asyncio.StreamWriter | None = None,
) -> None:
    if process.returncode is None:
        raise ProcessError("Owned pipes require verified process-group exit before release.")

    async def close_pipes() -> None:
        if stdin_writer is not None:
            stdin_writer.close()
            await asyncio.wait_for(stdin_writer.wait_closed(), timeout=LOCAL_IO_TIMEOUT_SEC)
        for transport, _reader in connections:
            transport.close()
        for _transport, reader in connections:
            await asyncio.wait_for(reader.read(), timeout=LOCAL_IO_TIMEOUT_SEC)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()

    closure = create_ephemeral_task(
        close_pipes(), name="core.system.managed-process-pipes", log_exceptions=False
    )
    try:
        try:
            await asyncio.shield(closure)
        finally:
            await wait_for_task_completion(closure, retain_resources_until_complete=True)
            closure.result()
    except TimeoutError as exception:
        raise ProcessGroupCleanupError(
            "Owned subprocess pipes did not verify closure before their deadline.",
            process=process,
            read_connections=connections,
            stdin_writer=stdin_writer,
            cause=exception,
        ) from exception
