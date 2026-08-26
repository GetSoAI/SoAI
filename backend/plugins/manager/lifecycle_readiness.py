"""SoAI - Plugin manager readiness helpers [backend/plugins/manager/lifecycle_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
from core.logging.trace import get_logger
from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = (
    "publish_readiness_degraded_override",
    "resolve_readiness_error",
)

LOGGER_NAME = "SoAI.plugins.manager.lifecycle_readiness"
OPERATION = "plugin_manager.publish_readiness_degraded_override"


def resolve_readiness_error(manager: PluginManagerLifecycleTarget) -> str | None:
    fatal_error = manager.state.lifecycle.fatal_readiness_error
    if isinstance(fatal_error, str) and fatal_error.strip():
        return fatal_error
    reconciliation_error = manager.state.lifecycle.initial_reconciliation_error
    if isinstance(reconciliation_error, str) and reconciliation_error.strip():
        return reconciliation_error
    return None


async def publish_readiness_degraded_override(
    manager: PluginManagerLifecycleTarget,
    *,
    reason: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if manager.state.lifecycle.readiness_degraded_published:
        return
    try:
        await manager.dependencies.infrastructure.event_bus.publish(
            SystemMainStateOverrideEvent(
                state=SoAIMainState.ERROR,
                duration_sec=30,
                reason=reason,
            ),
        )
        manager.state.lifecycle.readiness_degraded_published = True
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(
            exception,
            operation="plugin_manager.publish_readiness_degraded_override",
        )
        log_handled_exception(
            logger,
            error,
            message="Failed to publish plugin manager degraded-readiness override (non-critical).",
            operation=OPERATION,
            level="debug",
        )
