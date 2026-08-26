"""SoAI - PTY session storage for thread-safe session state management [backend/terminal/session_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terminal.types import PTYSession

__all__ = ("PTYSessionStore",)


class PTYSessionStore:

    def __init__(self) -> None:
        self._sessions: dict[str, PTYSession] = {}
        self.lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    async def register(self, session_id: str, session: PTYSession) -> None:
        async with self.lock:
            with self._sync_lock:
                self._sessions[session_id] = session

    async def unregister(self, session_id: str) -> PTYSession | None:
        async with self.lock:
            with self._sync_lock:
                return self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> PTYSession | None:
        with self._sync_lock:
            return self._sessions.get(session_id)

    def contains(self, session_id: str) -> bool:
        with self._sync_lock:
            return session_id in self._sessions

    def get_all_ids(self) -> list[str]:
        with self._sync_lock:
            return list(self._sessions.keys())

    def get_ids_for_user(self, user_id: int) -> list[str]:
        with self._sync_lock:
            return [
                session_id
                for session_id, session in self._sessions.items()
                if session.user_id == user_id
            ]

    def create_if_absent(
        self,
        session_id: str,
        factory: Callable[[], PTYSession],
    ) -> tuple[PTYSession, bool]:
        with self._sync_lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return (existing, False)
            session = factory()
            self._sessions[session_id] = session
            return (session, True)
