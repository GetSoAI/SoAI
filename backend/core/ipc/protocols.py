"""SoAI - IPC worker protocols [backend/core/ipc/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Protocol

__all__ = (
    "IpcConnectionWaitServerProtocol",
    "ManagedIpcWorkerDependenciesProtocol",
    "ManagedIpcWorkerFactoryProtocol",
    "ManagedIpcWorkerProtocol",
)


class IpcConnectionWaitServerProtocol(Protocol):
    async def wait_for_worker(self, worker_id: int, *, timeout_sec: float) -> None: ...


class ManagedIpcWorkerDependenciesProtocol(Protocol):
    @property
    def worker_id(self) -> int: ...

    @property
    def argv(self) -> Sequence[str]: ...

    @property
    def cwd(self) -> str: ...

    @property
    def env(self) -> Mapping[str, str]: ...

    @property
    def diagnostic_log_path(self) -> str: ...


class ManagedIpcWorkerProtocol(Protocol):
    worker_id: int
    process: asyncio.subprocess.Process | None

    async def spawn(
        self,
        *,
        server: IpcConnectionWaitServerProtocol,
        startup_timeout_sec: float,
    ) -> None: ...

    async def terminate(self, *, operation: str) -> None: ...


class ManagedIpcWorkerFactoryProtocol(Protocol):
    def create(self, deps: ManagedIpcWorkerDependenciesProtocol) -> ManagedIpcWorkerProtocol: ...
