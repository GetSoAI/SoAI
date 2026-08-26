"""SoAI - Execution cleanup and tracking finalization [backend/orchestrator/execution/engine_task_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from orchestrator.capacity.slot_lease import PluginSlotLease

if TYPE_CHECKING:
    from orchestrator.execution.internal_protocols import (
        ActiveInferenceRegistryProtocol,
    )
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )

__all__ = ("cleanup_task_execution",)


async def cleanup_task_execution(
    *,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    plugin_name: str,
    tracking_id: str | None,
    task_id: str,
    completed: bool,
    cancelled: bool,
    is_persistent: bool,
    active_registered: bool,
    slot_lease: PluginSlotLease | None,
) -> None:
    if active_registered and tracking_id is not None:
        duration = None
        dispatch_time = await active_inferences.get_dispatch_time(tracking_id)
        if dispatch_time is not None:
            duration = time.monotonic() - dispatch_time
        await lifecycle.task_tracking.register_task_finish(
            plugin_name,
            tracking_id,
            duration=duration,
            completed=completed,
            cancelled=cancelled,
            is_persistent=is_persistent,
            last_task_id=task_id,
        )
    if slot_lease is not None:
        slot_lease.release()
