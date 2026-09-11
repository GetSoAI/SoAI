"""SoAI - NVIDIA GPU state persistence helpers [backend/hardware/vendors/nvidia/persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from shutil import which
from typing import TYPE_CHECKING, Literal

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
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
    singleflight: SyncSingleflight[tuple[int, int, int, int], JSONDict]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NvidiaCapabilitiesCacheServiceDependencies",
            entries=self.entries,
            entries_lock=self.entries_lock,
            singleflight=self.singleflight,
        )


class NvidiaCapabilitiesCacheService:

    def __init__(self, deps: NvidiaCapabilitiesCacheServiceDependencies) -> None:
        self._entries = deps.entries
        self._entries_lock = deps.entries_lock
        self._singleflight = deps.singleflight
        self._generation = 0
        self._revision = 0
        self._vendor_generations: dict[int, int] = {}
        self._expiry = 0
        self._accepted_observation = 0
        self._signature: tuple[tuple[int, str, str, bool], ...] | None = None
        self._unfinished: tuple[str, ...] = ()

    def get_cached(self, vendor_id: int) -> JSONDict | None:
        with self._entries_lock:
            payload = self._entries.get(vendor_id)
            return copy.deepcopy(payload) if payload is not None else None

    def set_cached(self, vendor_id: int, payload: JSONDict) -> None:
        with self._entries_lock:
            self._revision += 1
            self._vendor_generations[vendor_id] = self._vendor_generations.get(vendor_id, 0) + 1
            self._entries[vendor_id] = copy.deepcopy(payload)

    def invalidate(self, vendor_id: int) -> None:
        with self._entries_lock:
            self._revision += 1
            self._vendor_generations[vendor_id] = self._vendor_generations.get(vendor_id, 0) + 1
            self._entries.pop(vendor_id, None)

    def clear(self) -> None:
        with self._entries_lock:
            self._entries.clear()
            self._generation += 1
            self._revision += 1
            self._vendor_generations.clear()

    def revision(self) -> int:
        with self._entries_lock:
            return self._revision

    def expiry_sequence(self) -> int:
        with self._entries_lock:
            return self._expiry

    def expire_inventory_snapshot(self) -> int:
        with self._entries_lock:
            self._entries.clear()
            self._expiry += 1
            return self._expiry

    def observe_inventory(
        self,
        sequence: int,
        status: Literal["complete", "partial", "failed"],
        gpus: list[JSONDict],
        driver_version: str,
    ) -> None:
        identities: list[tuple[int, str, str, bool]] = []
        settings_available = which("nvidia-settings") is not None
        for gpu in gpus:
            vendor_id = gpu.get("vendor_id")
            device_id = gpu.get("device_id")
            if not isinstance(vendor_id, int) or not isinstance(device_id, str) or not device_id:
                status = "partial"
                continue
            identities.append((vendor_id, device_id, driver_version, settings_available))
        if gpus and not driver_version:
            status = "partial"
        signature = tuple(sorted(identities)) if status == "complete" else None
        with self._entries_lock:
            if sequence <= self._accepted_observation:
                return
            self._accepted_observation = sequence
            if signature is None or self._signature != signature:
                self._generation += 1
                self._revision += 1
                self._entries.clear()
                self._vendor_generations.clear()
            self._signature = signature
            if signature is not None:
                present = {entry[1] for entry in signature}
                self._unfinished = tuple(
                    identity for identity in self._unfinished if identity in present
                )

    def inventory_available(self) -> bool:
        with self._entries_lock:
            return self._accepted_observation == 0 or self._signature is not None

    def unfinished_devices(self) -> tuple[str, ...]:
        with self._entries_lock:
            return self._unfinished

    def record_probe_progress(self, generation: int, unfinished: tuple[str, ...]) -> None:
        with self._entries_lock:
            if generation == self._revision:
                self._unfinished = unfinished

    def _authority_token_unlocked(self, vendor_id: int) -> tuple[int, int, int]:
        return (
            self._generation,
            self._vendor_generations.get(vendor_id, 0),
            vendor_id,
        )

    def _flight_token_unlocked(self, vendor_id: int) -> tuple[int, int, int, int]:
        authority = self._authority_token_unlocked(vendor_id)
        return (authority[0], authority[1], authority[2], self._expiry)

    def compute_or_wait(
        self,
        vendor_id: int,
        compute: Callable[[], JSONDict],
        *,
        deadline: MonotonicDeadline | None = None,
    ) -> JSONDict:
        if vendor_id < 0:
            raise ValidationError("vendor_id must be non-negative.")
        operation_deadline = deadline or deadline_after(10.0)
        for attempt in range(2):
            with self._entries_lock:
                cached = self._entries.get(vendor_id)
                if cached is not None:
                    return copy.deepcopy(cached)
                token = self._flight_token_unlocked(vendor_id)
                authority = self._authority_token_unlocked(vendor_id)

            def compute_and_store(
                captured_token: tuple[int, int, int, int] = token,
            ) -> JSONDict:
                payload = compute()
                with self._entries_lock:
                    if (
                        captured_token == self._flight_token_unlocked(vendor_id)
                        and operation_deadline.remaining_seconds() >= 1
                    ):
                        self._entries[vendor_id] = copy.deepcopy(payload)
                return payload

            payload = self._singleflight.execute_or_wait(
                token,
                compute_and_store,
                timeout=operation_deadline.remaining_seconds(),
            )
            with self._entries_lock:
                if authority == self._authority_token_unlocked(vendor_id):
                    return copy.deepcopy(payload)
            if attempt == 1 or operation_deadline.remaining_seconds() < 1:
                raise TimeoutError("NVIDIA capability observation was superseded.")
        raise TimeoutError("NVIDIA capability observation was superseded.")
