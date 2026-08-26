"""SoAI - Licensing startup repair-plane restart coordination [backend/app/licensing_repair_plane_coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.runtime.protocols import RuntimeRepairPlaneViewProtocol
from core.state.protocols import SystemRestartRequesterProtocol

_RESTART_REASON = "Licensing recovery completed; restart is required to start ordinary services."
_RESTART_SOURCE = "licensing_repair"


@dataclass(frozen=True, slots=True)
class LicensingRepairPlaneCoordinatorDependencies:
    runtime_state: RuntimeRepairPlaneViewProtocol
    restart_requester: SystemRestartRequesterProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LicensingRepairPlaneCoordinatorDependencies",
            restart_requester=self.restart_requester,
            runtime_state=self.runtime_state,
        )


class LicensingRepairPlaneCoordinator:
    def __init__(self, deps: LicensingRepairPlaneCoordinatorDependencies) -> None:
        self._deps = deps
        self._lock = asyncio.Lock()
        self._licensing_startup_repair_plane = False

    @property
    def startup_repair_plane_active(self) -> bool:
        return self._licensing_startup_repair_plane

    async def activate_startup_repair_plane(self) -> None:
        async with self._lock:
            self._licensing_startup_repair_plane = True

    async def reconcile(self, dynamic_requires_repair_plane: bool) -> None:
        startup_repair_plane = self._deps.runtime_state.repair_plane
        if (
            dynamic_requires_repair_plane
            or not startup_repair_plane
            or not self._licensing_startup_repair_plane
        ):
            return
        async with self._lock:
            if not self._deps.runtime_state.restart_pending.is_set():
                await self._deps.restart_requester.require_restart(
                    _RESTART_REASON,
                    _RESTART_SOURCE,
                )


__all__ = (
    "LicensingRepairPlaneCoordinator",
    "LicensingRepairPlaneCoordinatorDependencies",
)
