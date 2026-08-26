"""SoAI - Plugin previous state resolution [backend/plugins/loader/loading_previous_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.state.state_names import (
    PLUGIN_STATE_NOT_DETECTED,
    PluginRuntimeStateName,
    resolve_plugin_runtime_state_name,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("resolve_previous_plugin_state",)

OPERATION = "plugin_loader.load_and_announce_plugin"


async def resolve_previous_plugin_state(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    existing_record: JSONDict | None,
    logger: LoggerProtocol,
) -> PluginRuntimeStateName:
    if existing_record and existing_record.get("state"):
        state_value = existing_record.get("state")
        if isinstance(state_value, str) and state_value:
            resolved_state = resolve_plugin_runtime_state_name(state_value)
            if resolved_state is None:
                raise StateError(
                    "Invalid persisted plugin runtime state.",
                    operation="plugin_loader.load_and_announce_plugin",
                    details={"plugin_name": plugin_name, "status": state_value},
                )
            return resolved_state
    if manager.dependencies.infrastructure.state_aggregator is not None:
        try:
            return await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
                plugin_name,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to retrieve previous plugin state from aggregator (non-critical).",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="debug",
            )
    return PLUGIN_STATE_NOT_DETECTED
