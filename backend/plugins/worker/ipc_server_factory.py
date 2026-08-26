"""SoAI - Plugin worker IPC server construction [backend/plugins/worker/ipc_server_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.config.protocols import ConfigProtocol
from core.ipc.multiplexed import MultiplexedIpcServer
from core.ipc.ndjson import NdjsonCodec
from core.ipc.settings import resolve_ipc_max_message_bytes
from core.types.json import JSONDict

__all__ = ("build_plugin_worker_ipc_server",)


def build_plugin_worker_ipc_server(
    *,
    encoding_pool: BoundedBlockingPool,
    config: ConfigProtocol,
    host_request_handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]],
) -> MultiplexedIpcServer:
    return MultiplexedIpcServer(
        encoding_pool=encoding_pool,
        codec=NdjsonCodec(max_line_bytes=resolve_ipc_max_message_bytes(config)),
        host_request_handler=host_request_handler,
    )
