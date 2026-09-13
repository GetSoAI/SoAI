"""SoAI - Plugin backend lifecycle runtime-state validation [backend/plugins/actions/backend_lifecycle_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.persistent_runtime_truth import (
    get_plugin_status_payload,
    resolve_persistent_runtime_state,
)
from core.state.state_names import (
    PLUGIN_STATE_STOPPED,
    resolve_plugin_runtime_state_name,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.state_names import PluginRuntimeStateName

__all__ = ("require_runtime_state", "resolve_retained_backend_state")

OPERATION_RETAINED_BACKEND = "plugins.actions.backend_lifecycle_state.retained_backend"
RETAINED_BACKEND_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, OSError)


async def resolve_retained_backend_state(
    instance: PluginInstanceProtocol | None,
    *,
    fallback_state: PluginRuntimeStateName,
    absent_state: PluginRuntimeStateName,
    logger: LoggerProtocol,
) -> PluginRuntimeStateName:
    if instance is None:
        return fallback_state
    try:
        status = await get_plugin_status_payload(
            instance, operation=OPERATION_RETAINED_BACKEND, logger=logger, raise_on_error=True
        )
        if status.get("installed") is False:
            return absent_state
        if status.get("installed") is not True:
            return fallback_state
        if instance.PERSISTENT:
            state, _, _ = await resolve_persistent_runtime_state(
                instance,
                attempt_activate=False,
                failure_state=fallback_state,
                operation=OPERATION_RETAINED_BACKEND,
                logger=logger,
                status_payload=status,
            )
            return state
        if await instance.get_backend_process_pids():
            if not await instance.stop():
                return fallback_state
            if await instance.get_backend_process_pids():
                return fallback_state
        return PLUGIN_STATE_STOPPED
    except RETAINED_BACKEND_FAILURES as exception:
        log_exception(
            logger,
            exception,
            message="Retained backend state could not be verified.",
            operation=OPERATION_RETAINED_BACKEND,
            level="warning",
        )
    return fallback_state


def require_runtime_state(
    state_name: str,
    *,
    operation: str,
    plugin_name: str,
    trace_id: str,
) -> PluginRuntimeStateName:
    resolved = resolve_plugin_runtime_state_name(state_name)
    if resolved is None:
        raise StateError(
            "Invalid persisted plugin runtime state.",
            operation=operation,
            details={"plugin_name": plugin_name, "status": state_name, "trace_id": trace_id},
        )
    return resolved
