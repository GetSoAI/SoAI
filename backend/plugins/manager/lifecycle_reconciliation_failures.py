"""SoAI - Plugin manager reconciliation failure handling [backend/plugins/manager/lifecycle_reconciliation_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.runtime.soai_identifiers import create_system_id
from plugins.manager.lifecycle_readiness import publish_readiness_degraded_override
from plugins.manager.lifecycle_startup_result import mark_initial_reconciliation_failed

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = (
    "handle_initial_reconciliation_handled_failure",
    "handle_initial_reconciliation_unexpected_failure",
)

OPERATION_PLUGIN_MANAGER_RUN_INITIAL_RECONCILIATION = "plugin_manager.run_initial_reconciliation"


async def _record_initial_reconciliation_failure(
    manager: PluginManagerLifecycleTarget,
    logger: LoggerProtocol,
    exception: Exception,
    *,
    message: str,
) -> None:
    trace_id = create_system_id(
        subsystem="plugin_reconcile",
        owner="initial",
        include_random_suffix=True,
    )
    log_exception(
        logger,
        exception,
        message=message,
        trace_id=trace_id,
        operation=OPERATION_PLUGIN_MANAGER_RUN_INITIAL_RECONCILIATION,
        level="critical",
    )
    mark_initial_reconciliation_failed(
        manager,
        f"{trace_id}: {type(exception).__name__}: {exception}",
    )
    await publish_readiness_degraded_override(
        manager,
        reason="Plugin manager reconciliation failed. Plugin subsystem is degraded.",
    )


async def handle_initial_reconciliation_handled_failure(
    manager: PluginManagerLifecycleTarget,
    logger: LoggerProtocol,
    exception: Exception,
) -> None:
    await _record_initial_reconciliation_failure(
        manager,
        logger,
        exception,
        message="Initial plugin reconciliation failed",
    )


async def handle_initial_reconciliation_unexpected_failure(
    manager: PluginManagerLifecycleTarget,
    logger: LoggerProtocol,
    exception: Exception,
) -> None:
    coerced = coerce_to_soai_error(
        exception,
        operation=OPERATION_PLUGIN_MANAGER_RUN_INITIAL_RECONCILIATION,
    )
    await _record_initial_reconciliation_failure(
        manager,
        logger,
        coerced,
        message="Initial plugin reconciliation failed unexpectedly",
    )
