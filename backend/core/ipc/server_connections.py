"""SoAI - IPC server worker connection registry [backend/core/ipc/server_connections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.ipc.stream_closing import close_ipc_writer

__all__ = (
    "WorkerConnection",
    "WorkerConnectionIndex",
)


@dataclass(slots=True)
class WorkerConnection:
    worker_id: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    lock: asyncio.Lock


class WorkerConnectionIndex:
    def __init__(self) -> None:
        self._connections: dict[int, WorkerConnection] = {}
        self._lock = asyncio.Lock()

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            await close_ipc_writer(connection.writer, worker_id=int(connection.worker_id))

    async def get(self, worker_id: int) -> WorkerConnection | None:
        async with self._lock:
            return self._connections.get(int(worker_id))

    async def replace(self, connection: WorkerConnection) -> WorkerConnection | None:
        async with self._lock:
            worker_id = int(connection.worker_id)
            old = self._connections.get(worker_id)
            self._connections[worker_id] = connection
            return old

    async def drop(
        self,
        worker_id: int,
        *,
        writer: asyncio.StreamWriter | None,
    ) -> WorkerConnection | None:
        async with self._lock:
            existing = self._connections.get(int(worker_id))
            if existing is None:
                return None
            if writer is not None and existing.writer is not writer:
                return None
            self._connections.pop(int(worker_id), None)
            return existing

    async def drop_if_matches(self, worker_id: int, *, writer: asyncio.StreamWriter) -> None:
        async with self._lock:
            current = self._connections.get(int(worker_id))
            if current is not None and current.writer is writer:
                self._connections.pop(int(worker_id), None)
