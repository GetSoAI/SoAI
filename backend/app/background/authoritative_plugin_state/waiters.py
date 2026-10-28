"""SoAI - Authoritative plugin state completion waiters [backend/app/background/authoritative_plugin_state/waiters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.publication_errors import (
    AuthoritativePluginStateCompletion,
    PublicationFailedError,
)

__all__ = ("AuthoritativePluginStateCompletion", "AuthoritativePluginStateWaiters")


class AuthoritativePluginStateWaiters:
    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Future[AuthoritativePluginStateCompletion]] = {}
        self._lock = asyncio.Lock()

    async def create(self, event_id: str) -> asyncio.Future[AuthoritativePluginStateCompletion]:
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[AuthoritativePluginStateCompletion] = loop.create_future()
        async with self._lock:
            existing_waiter = self._waiters.get(event_id)
            if existing_waiter is not None and not existing_waiter.done():
                raise PublicationFailedError(
                    "Duplicate authoritative plugin state waiter.",
                    operation="authoritative_plugin_state_waiters.create",
                    details={"event_id": event_id},
                )
            self._waiters[event_id] = waiter
        return waiter

    async def resolve_success(self, event_id: str) -> None:
        waiter = await self._pop(event_id)
        if waiter is None or waiter.done():
            return
        waiter.set_result(AuthoritativePluginStateCompletion(event_id))

    async def resolve_failure(self, event_id: str, message: str) -> None:
        waiter = await self._pop(event_id)
        if waiter is None or waiter.done():
            return
        waiter.set_result(
            AuthoritativePluginStateCompletion(
                event_id,
                str(message),
            ),
        )

    async def discard(self, event_id: str) -> None:
        await self._pop(event_id)

    async def resolve_shutdown(self) -> None:
        async with self._lock:
            waiters = list(self._waiters.items())
            self._waiters.clear()
        for event_id, waiter in waiters:
            if waiter.done():
                continue
            waiter.set_result(
                AuthoritativePluginStateCompletion(
                    event_id,
                    "Authoritative plugin state dispatcher shut down before delivery completed.",
                ),
            )

    async def _pop(
        self, event_id: str
    ) -> asyncio.Future[AuthoritativePluginStateCompletion] | None:
        async with self._lock:
            return self._waiters.pop(event_id, None)
