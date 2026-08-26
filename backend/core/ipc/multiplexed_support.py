"""SoAI - Multiplexed IPC support primitives [backend/core/ipc/multiplexed_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.ipc.stream_closing import close_ipc_writer
from core.types.json import JSONDict

__all__ = (
    "MultiplexedConnection",
    "close_connection",
    "fail_pending",
    "require_ipc_text",
    "validate_hello",
)


@dataclass(slots=True)
class MultiplexedConnection:
    worker_id: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    write_lock: asyncio.Lock
    pending: dict[str, asyncio.Future[JSONDict]] = field(
        default_factory=dict[str, asyncio.Future[JSONDict]],
    )
    event_handlers: dict[str, Callable[[JSONDict], Awaitable[None]]] = field(
        default_factory=dict[str, Callable[[JSONDict], Awaitable[None]]],
    )


def require_ipc_text(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError(f"{label} is required for IPC request.")
    return normalized


def fail_pending(connection: MultiplexedConnection, message: str) -> None:
    for future in list(connection.pending.values()):
        if not future.done():
            future.set_exception(
                ServiceUnavailableError(
                    message,
                    operation="core.ipc.multiplexed.connection_drop",
                    details={"worker_id": int(connection.worker_id)},
                ),
            )
    connection.pending.clear()
    connection.event_handlers.clear()


async def close_connection(connection: MultiplexedConnection) -> None:
    fail_pending(connection, "IPC worker connection closed.")
    await close_ipc_writer(connection.writer, worker_id=connection.worker_id)


def validate_hello(hello: JSONDict, token: str) -> tuple[int, str | None]:
    if hello.get("type") != "hello":
        raise ValidationError("IPC hello message type mismatch.")
    if str(hello.get("token") or "") != token:
        raise ValidationError("IPC token mismatch.")
    worker_id_raw = hello.get("worker_id")
    if not isinstance(worker_id_raw, int):
        raise ValidationError("IPC worker_id must be an integer.")
    worker_secret_raw = hello.get("worker_secret")
    if worker_secret_raw is None:
        worker_secret = None
    elif isinstance(worker_secret_raw, str):
        worker_secret = worker_secret_raw.strip() or None
    else:
        raise ValidationError("IPC worker_secret must be a string.")
    return int(worker_id_raw), worker_secret
