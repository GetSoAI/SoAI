"""SoAI - NVIDIA GPU state persistence helpers [backend/hardware/vendors/nvidia/persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.singleflight import SyncSingleflight
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.types.json import JSONDict

__all__ = (
    "NvidiaCapabilitiesCacheService",
    "NvidiaCapabilitiesCacheServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class NvidiaCapabilitiesCacheServiceDependencies:
    entries: dict[int, JSONDict]
    entries_lock: threading.Lock
    singleflight: SyncSingleflight[int, JSONDict]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NvidiaCapabilitiesCacheServiceDependencies",
            entries=self.entries,
            entries_lock=self.entries_lock,
            singleflight=self.singleflight,
        )


class NvidiaCapabilitiesCacheService:
    __slots__ = ("_entries", "_entries_lock", "_singleflight")

    def __init__(self, deps: NvidiaCapabilitiesCacheServiceDependencies) -> None:
        self._entries = deps.entries
        self._entries_lock = deps.entries_lock
        self._singleflight = deps.singleflight

    def get_cached(self, vendor_id: int) -> JSONDict | None:
        with self._entries_lock:
            payload = self._entries.get(vendor_id)
            return copy.deepcopy(payload) if payload is not None else None

    def set_cached(self, vendor_id: int, payload: JSONDict) -> None:
        with self._entries_lock:
            self._entries[vendor_id] = copy.deepcopy(payload)

    def invalidate(self, vendor_id: int) -> None:
        with self._entries_lock:
            self._entries.pop(vendor_id, None)

    def clear(self) -> None:
        with self._entries_lock:
            self._entries.clear()

    def compute_or_wait(self, vendor_id: int, compute: Callable[[], JSONDict]) -> JSONDict:
        if vendor_id < 0:
            raise ValidationError("vendor_id must be non-negative.")
        cached = self.get_cached(vendor_id)
        if cached is not None:
            return cached

        def _compute_and_store() -> JSONDict:
            payload = compute()
            self.set_cached(vendor_id, payload)
            return payload

        return self._singleflight.execute_or_wait(vendor_id, _compute_and_store)
