"""SoAI - Hardware activity lease protocol definitions [backend/core/hardware/protocols_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ()


class HardwareActivityLeaseProtocol(Protocol):
    @property
    def device_id(self) -> str: ...

    @property
    def lease_id(self) -> str: ...

    @property
    def activity_type(self) -> str: ...

    @property
    def owner_id(self) -> str: ...

    @property
    def run_id(self) -> str | None: ...


class HardwareActivityConflictProtocol(Protocol):
    @property
    def device_id(self) -> str: ...

    @property
    def active_activity_type(self) -> str: ...

    @property
    def conflict_reason(self) -> str: ...


class HardwareActivityAcquireResultProtocol(Protocol):
    @property
    def lease(self) -> HardwareActivityLeaseProtocol | None: ...

    @property
    def conflict(self) -> HardwareActivityConflictProtocol | None: ...


class HardwareActivityRegistryProtocol(Protocol):
    async def acquire(
        self,
        *,
        device_id: str,
        activity_type: str,
        owner_id: str,
        conflict_reason: str,
    ) -> HardwareActivityAcquireResultProtocol: ...

    async def bind_run_id(self, *, device_id: str, lease_id: str, run_id: str) -> bool: ...

    async def release(self, *, device_id: str, lease_id: str) -> bool: ...

    async def clear(self) -> None: ...
