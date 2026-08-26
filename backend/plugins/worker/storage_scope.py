"""SoAI - Worker request-scoped storage reservation tokens [backend/plugins/worker/storage_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = (
    "ActiveStorageReservationScope",
    "WorkerStorageScopeState",
)


@dataclass(frozen=True, slots=True)
class ActiveStorageReservationScope:
    reservation_id: str
    reservation_root: str


class WorkerStorageScopeState:
    __slots__ = ("_active_scope",)

    def __init__(self) -> None:
        self._active_scope: ContextVar[ActiveStorageReservationScope | None] = ContextVar(
            "soai_active_storage_reservation_scope",
            default=None,
        )

    def get_active_scope(self) -> ActiveStorageReservationScope | None:
        return self._active_scope.get()

    @contextmanager
    def active_scope(
        self,
        reservation_id: str | None,
        reservation_root: str | None,
    ) -> Generator[None]:
        if (reservation_id is None) != (reservation_root is None):
            raise ValidationError(
                "Storage reservation scope requires both reservation_id and reservation_root.",
            )
        scope = (
            ActiveStorageReservationScope(
                reservation_id=reservation_id,
                reservation_root=reservation_root,
            )
            if reservation_id is not None and reservation_root is not None
            else None
        )
        token = self._active_scope.set(scope)
        try:
            yield
        finally:
            self._active_scope.reset(token)
