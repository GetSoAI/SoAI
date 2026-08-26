"""SoAI - Managed IPC worker startup waiting [backend/core/ipc/managed_worker_startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exceptions import ProcessError
from core.ipc.protocols import IpcConnectionWaitServerProtocol

__all__ = ("wait_for_worker_or_exit",)


async def wait_for_worker_or_exit(
    server: IpcConnectionWaitServerProtocol,
    *,
    worker_id: int,
    process: asyncio.subprocess.Process,
    diagnostic_log_path: str,
    startup_timeout_sec: float,
) -> None:
    worker_id_value = int(worker_id)
    timeout_value = max(0.1, float(startup_timeout_sec))
    wait_connected = create_ephemeral_task(
        server.wait_for_worker(worker_id_value, timeout_sec=timeout_value),
    )
    wait_exited = create_ephemeral_task(process.wait())
    try:
        done, _ = await asyncio.wait(
            {wait_connected, wait_exited},
            return_when=asyncio.FIRST_COMPLETED,
            timeout=timeout_value,
        )
        if wait_connected in done:
            wait_connected.result()
            return
        if wait_exited in done:
            returncode = process.returncode
            if returncode is None:
                try:
                    returncode = int(wait_exited.result())
                except (ValueError, TypeError):
                    returncode = None
            raise ProcessError(
                "IPC worker exited before connecting.",
                operation="core.ipc.managed_worker.spawn.exited_before_connect",
                details={
                    "diagnostic_log_path": diagnostic_log_path,
                    "worker_id": worker_id_value,
                    "returncode": returncode,
                },
            )
        raise ProcessError(
            "IPC worker did not connect within startup timeout.",
            operation="core.ipc.managed_worker.spawn.connect_timeout",
            details={
                "diagnostic_log_path": diagnostic_log_path,
                "worker_id": worker_id_value,
                "timeout_sec": timeout_value,
            },
        )
    finally:
        await cancel_and_await(
            (wait_connected, wait_exited),
            task_label="IPC worker connect wait tasks",
        )
        for task in (wait_connected, wait_exited):
            if task.cancelled():
                continue
            exception = task.exception()
            if exception is not None:
                raise exception
