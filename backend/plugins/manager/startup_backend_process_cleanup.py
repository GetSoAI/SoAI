"""SoAI - Startup backend process cleanup for tracking-enabled plugins [backend/plugins/manager/startup_backend_process_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.runtime.backend_process_tracking_db import (
    cleanup_all_tracked_backend_processes_from_database,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("cleanup_startup_tracked_backend_processes",)


async def cleanup_startup_tracked_backend_processes(
    manager: PluginManagerRuntimeProtocol,
    *,
    logger: LoggerProtocol,
) -> None:
    failures = await cleanup_all_tracked_backend_processes_from_database(
        manager.dependencies.databases.plugins,
        logger=logger,
    )
    if not failures:
        return
    first_failure = failures[0]
    raise StateError(
        "Startup backend cleanup failed for a tracked plugin backend process.",
        operation="plugin_manager.initialize.startup_backend_cleanup",
        details={
            "plugin_name": first_failure.plugin_name,
            "failed": first_failure.failed_payload,
        },
    )
