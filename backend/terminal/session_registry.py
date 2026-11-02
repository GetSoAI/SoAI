"""SoAI - PTY session storage for thread-safe session state management [backend/terminal/session_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError
from core.mutations.identifiers import (
    extract_mutation_request_timestamp_ms,
    require_mutation_request_id,
)
from core.mutations.identity_window import IDENTITY_MAX_SKEW_MS, validate_mutation_identity_window
from core.terminal.acquisition_errors import PTYAcquisitionError
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from terminal.types import PTYSession

__all__ = ("PTYSessionStore",)


@dataclass(slots=True)
class PTYAcquisition:
    user_id: int
    admission_until_ms: int
    session_id: str | None = None
    released: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class PTYSessionStore:

    def __init__(self) -> None:
        self._sessions: dict[str, PTYSession] = {}
        self.lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        self._acquisitions: dict[str, PTYAcquisition] = {}

    def reserve_acquisition(
        self, acquisition_id: str, user_id: int, *, allow_new: bool = True
    ) -> PTYAcquisition:
        require_mutation_request_id(acquisition_id)
        existing = self._acquisitions.get(acquisition_id)
        if existing is not None:
            if existing.user_id != user_id:
                raise PTYAcquisitionError("PTY acquisition owner does not match.")
            return existing
        if not allow_new:
            raise SecurityError("Terminal permission is required to reserve an acquisition.")
        now_ms = epoch_ms()
        validate_mutation_identity_window(acquisition_id, now_ms)
        for identity, acquisition in tuple(self._acquisitions.items()):
            if (
                acquisition.released
                and not acquisition.lock.locked()
                and acquisition.admission_until_ms < now_ms
            ):
                del self._acquisitions[identity]
        if len(self._acquisitions) >= 4096:
            raise PTYAcquisitionError(
                "PTY acquisition capacity is exhausted. Retry after releasing existing terminals."
            )
        acquisition = PTYAcquisition(
            user_id=user_id,
            admission_until_ms=extract_mutation_request_timestamp_ms(acquisition_id)
            + IDENTITY_MAX_SKEW_MS,
        )
        self._acquisitions[acquisition_id] = acquisition
        return acquisition

    async def register(self, session_id: str, session: PTYSession) -> None:
        async with self.lock:
            with self._sync_lock:
                self._sessions[session_id] = session

    async def unregister(self, session_id: str) -> PTYSession | None:
        async with self.lock:
            with self._sync_lock:
                session = self._sessions.get(session_id)
                if session is not None and session.acquisition_id is not None:
                    acquisition = self._acquisitions[session.acquisition_id]
                    if (
                        acquisition.session_id != session_id
                        or acquisition.user_id != session.user_id
                    ):
                        raise PTYAcquisitionError(
                            "PTY session acquisition ownership is inconsistent."
                        )
                    acquisition.released = True
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
