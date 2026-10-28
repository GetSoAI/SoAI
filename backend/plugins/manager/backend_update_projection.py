"""SoAI - Backend update catalog snapshots and lifecycle policy [backend/plugins/manager/backend_update_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.deadlines import deadline_after
from core.config.locks import PluginConfigurationBusyError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.backend_update_records import BackendUpdateRecord
from core.state.state_names import PLUGIN_STATE_BACKEND_NOT_INSTALLED, PLUGIN_STATE_NOT_DETECTED
from core.types.json import JSONDict
from core.validation.booleans import parse_bool
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.manager.backend_update_identity import capture_backend_update_identity
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("project_backend_updates", "read_backend_update_catalog")

OPERATION = "plugins.manager.backend_update_projection"
IDENTITY_LOCK_WAIT_BUDGET_SECONDS = 30.0
PROJECTION_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, SoAIError)


async def read_backend_update_catalog(
    manager: PluginManagerRuntimeProtocol,
) -> tuple[list[JSONDict], dict[str, BackendUpdateRecord] | None]:
    try:
        return await manager.dependencies.databases.plugins.get_backend_update_catalog()
    except PROJECTION_FAILURES as exception:
        log_exception(
            manager.logger,
            exception,
            message="Backend update catalog state is unavailable.",
            operation=OPERATION,
        )
        return await manager.dependencies.databases.plugins.get_all_listable_plugins(), None


async def project_backend_updates(
    manager: PluginManagerRuntimeProtocol,
    plugin_records: list[JSONDict],
    records: dict[str, BackendUpdateRecord] | None,
) -> dict[str, JSONDict]:
    snapshots: dict[str, JSONDict] = {}
    identity_lock_deadline = deadline_after(IDENTITY_LOCK_WAIT_BUDGET_SECONDS)
    for plugin in plugin_records:
        plugin_name = plugin.get("plugin_name")
        if not isinstance(plugin_name, str):
            continue
        snapshot: JSONDict = {
            "status": "none",
            "current_version": None,
            "latest_version": None,
            "checked_at_ms": None,
            "auto_update_failed": False,
            "can_update": False,
        }
        snapshots[plugin_name] = snapshot
        if not parse_bool(plugin.get("supports_backend_installation"), default=False):
            continue
        snapshot["can_update"] = await validate_action_for_state_async(
            manager,
            plugin_name,
            "update_backend",
            asyncio.Queue(),
            emit_error_event=False,
            finalize_task=False,
        )
        state_value = plugin.get("state")
        state = state_value if isinstance(state_value, str) else ""
        if state in {PLUGIN_STATE_BACKEND_NOT_INSTALLED, PLUGIN_STATE_NOT_DETECTED}:
            continue
        snapshot["status"] = (
            "unavailable"
            if records is None or manager.state.catalog.backend_update_degraded
            else "check_pending"
        )
        record = records.get(plugin_name) if records is not None else None
        if record is None:
            continue
        if identity_lock_deadline.expired():
            _mark_identity_unvalidated(snapshot)
            continue
        try:
            async with (
                manager.dependencies.infrastructure.config_manager.plugin_config_mutation_scope(
                    plugin_name, operation=OPERATION, deadline=identity_lock_deadline
                )
            ):
                identity = await capture_backend_update_identity(
                    manager, plugin_name, require_loaded_hash=False
                )
                if identity != record.identity:
                    continue
        except PluginConfigurationBusyError:
            _mark_identity_unvalidated(snapshot)
            continue
        except PROJECTION_FAILURES as exception:
            snapshot["status"] = "unavailable"
            log_exception(
                manager.logger,
                exception,
                message="Backend update identity is unavailable.",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
            )
            continue
        snapshot.update(
            {
                "status": (
                    "unavailable"
                    if record.status == "check_pending"
                    and manager.state.catalog.backend_update_degraded
                    else record.status
                ),
                "current_version": record.current_version,
                "latest_version": record.latest_version,
                "checked_at_ms": record.checked_at_ms,
                "auto_update_failed": record.auto_update_failed,
            }
        )
    return snapshots


def _mark_identity_unvalidated(snapshot: JSONDict) -> None:
    snapshot["status"] = "unavailable"
    snapshot["can_update"] = False
