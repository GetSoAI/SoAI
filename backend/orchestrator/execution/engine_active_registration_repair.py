"""SoAI - Active inference membership repair during engine cleanup [backend/orchestrator/execution/engine_active_registration_repair.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )

__all__ = ("repair_active_registered_from_membership",)

OPERATION = "orchestrator.task_execution"


async def repair_active_registered_from_membership(
    *,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    plugin_name: str,
    tracking_id: str | None,
    active_registered: bool,
    logger: TraceLogger,
    task_id: str,
) -> bool:
    if active_registered or tracking_id is None:
        return active_registered
    try:
        plugin_state = await lifecycle.watchers.get_plugin_state(plugin_name)
        if plugin_state is not None and tracking_id in plugin_state.active_tasks:
            return True
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message=(
                "Failed checking active task tracking during cancellation cleanup "
                "(non-critical)."
            ),
            operation=OPERATION,
            details={"task_id": task_id, "plugin": plugin_name},
            level="debug",
        )
    return active_registered
