"""SoAI - Discovery HTTP server blocking runtime helpers [backend/app/lifecycle/discovery_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Event

from app.lifecycle.discovery_http_server import DiscoveryHTTPServer

__all__ = (
    "DiscoveryServerThreadState",
    "create_discovery_server_thread_state",
    "serve_discovery_server",
    "shutdown_discovery_server",
)


@dataclass(frozen=True, slots=True)
class DiscoveryServerThreadState:
    started: Event
    stop_requested: Event


def create_discovery_server_thread_state() -> DiscoveryServerThreadState:
    return DiscoveryServerThreadState(started=Event(), stop_requested=Event())


def serve_discovery_server(
    server: DiscoveryHTTPServer,
    state: DiscoveryServerThreadState,
) -> None:
    if state.stop_requested.is_set():
        return
    state.started.set()
    if state.stop_requested.is_set():
        return
    server.serve_forever()


async def shutdown_discovery_server(
    server: DiscoveryHTTPServer,
    state: DiscoveryServerThreadState,
) -> None:
    state.stop_requested.set()
    if state.started.is_set():
        await asyncio.to_thread(server.shutdown)
