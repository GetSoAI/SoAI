"""SoAI - Authenticated SoAIBench child process startup [backend/hardware/soaibench/opencl_child_startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import secrets
import sys

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.soaibench_limits import MAX_CHILD_MESSAGE_BYTES
from core.ipc.multiplexed import MultiplexedIpcServer
from core.logging.protocols import LoggerProtocol
from core.system.async_process_spawning import (
    ManagedAsyncProcess,
    spawn_async_process,
    spawn_managed_async_process,
)
from core.system.bounded_stream_tail import BoundedStreamTail
from core.system.native_runtime_probes import interpreter_image_allowance
from hardware.soaibench.opencl_child import SoAIBenchOpenCLChild

__all__ = ("spawn_soaibench_opencl_child",)

CHILD_STARTUP_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


async def spawn_soaibench_opencl_child(
    logger: LoggerProtocol,
    numerical_validation_pool: BoundedBlockingPool,
    server: MultiplexedIpcServer,
    worker_id: int,
    *,
    cleanup_pool: BoundedBlockingPool | None = None,
) -> SoAIBenchOpenCLChild:
    await server.start()
    secret = secrets.token_hex(32)
    await server.expect_worker_secret(worker_id, worker_secret=secret)
    environment = {
        **os.environ,
        "SOAI_IPC_HOST": server.host,
        "SOAI_IPC_PORT": str(server.port),
        "SOAI_IPC_TOKEN": server.token,
        "SOAI_IPC_WORKER_ID": str(worker_id),
        "SOAI_IPC_WORKER_SECRET": secret,
    }
    process: asyncio.subprocess.Process | ManagedAsyncProcess
    try:
        startup_allowance = await asyncio.to_thread(
            interpreter_image_allowance, sys.executable, ordinary_seconds=0.0, environment=True
        )
        if os.name != "nt":
            process = await spawn_managed_async_process(
                [sys.executable, "-m", "hardware.soaibench.opencl_child_main"],
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=MAX_CHILD_MESSAGE_BYTES,
            )
        else:
            process = await spawn_async_process(
                [sys.executable, "-m", "hardware.soaibench.opencl_child_main"],
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name != "nt",
                limit=MAX_CHILD_MESSAGE_BYTES,
            )
    except CHILD_STARTUP_EXCEPTIONS:
        await server.forget_worker_secret(worker_id)
        raise
    diagnostics: list[tuple[BoundedStreamTail, asyncio.Task[None]]] = []
    readers = (
        (process.stdout_reader, process.stderr_reader)
        if isinstance(process, ManagedAsyncProcess)
        else (process.stdout, process.stderr)
    )
    for reader in readers:
        if reader is not None:
            tail = BoundedStreamTail(MAX_CHILD_MESSAGE_BYTES)
            pump = create_ephemeral_task(
                tail.drain(reader), name=f"soaibench-diagnostics-{worker_id}", log_exceptions=False
            )
            diagnostics.append((tail, pump))
    return SoAIBenchOpenCLChild(
        process,
        logger,
        numerical_validation_pool,
        server,
        worker_id,
        tuple(diagnostics),
        cleanup_pool=cleanup_pool,
        startup_allowance_seconds=startup_allowance.seconds,
    )
