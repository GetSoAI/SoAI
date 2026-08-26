"""SoAI - Orchestrator recovery queue purge binder [backend/app/composition/orchestrator_recovery_purge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.tasks.protocols import RecoveryQueuePurgeProtocol
from orchestrator.control.plugin_queue_purge import (
    purge_plugin_requests_from_global_queues,
)
from orchestrator.control.plugin_queue_purge_dependencies import (
    PluginQueuePurgeDependencies,
)

__all__ = ("build_recovery_queue_purge_callback",)


def build_recovery_queue_purge_callback(
    purge_deps: PluginQueuePurgeDependencies,
) -> RecoveryQueuePurgeProtocol:
    async def recovery_queue_purge(*, plugin_name: str, reason: str) -> None:
        await purge_plugin_requests_from_global_queues(
            deps=purge_deps,
            plugin_name=plugin_name,
            purge_reason=reason,
            fail_reason=reason,
            error_type=ErrorType.PLUGIN_UNAVAILABLE,
            operation="orchestrator.recovery_purge",
            allow_failover=True,
        )

    return recovery_queue_purge
