"""SoAI - Sequential plugin backend update batches [backend/plugins/actions/backend_bulk_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import UpdateAllPluginBackendsCommand
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from core.types.json import JSONDict, JSONValue
from plugins.actions.backend_update_children import update_backend_child
from plugins.actions.progress import (
    notify_operation_cancelled,
    send_completion_with_task,
    send_progress_with_task,
    send_unexpected_error_completion_for_plugin_manager,
)
from plugins.context_ids import resolve_task_id_from_context, resolve_user_id_from_context
from plugins.manager.backend_update_checks import check_backend_update
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
from plugins.state.task_collisions import handle_plugin_manager_task_id_collision

__all__ = ()

LOGGER_NAME = "SoAI.plugins.actions.backend_bulk_update"
OPERATION = "plugin_flow.process_update_all_backends_async"
BULK_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, SoAIError)


async def _update_one_plugin(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    parent_task_id: str,
    *,
    has_reserved_child: bool,
) -> JSONDict:
    if has_reserved_child:
        return {
            "plugin": plugin_name,
            "outcome": await update_backend_child(manager, parent_task_id, plugin_name),
        }
    check = await check_backend_update(manager, plugin_name, refresh=False)
    error = check.get("error")
    if error is not None:
        code = error.get("code") if isinstance(error, dict) else "invalid_response"
        outcome = (
            "deferred" if code in ("locked", "conflict", "deferred", "superseded") else "failed"
        )
        return {"plugin": plugin_name, "outcome": outcome, "reason": code}
    if check.get("installed") is False:
        return {"plugin": plugin_name, "outcome": "skipped", "reason": "backend_absent"}
    available = check.get("update_available")
    if available is False:
        return {"plugin": plugin_name, "outcome": "current"}
    if available is not True:
        return {"plugin": plugin_name, "outcome": "failed", "reason": "invalid_response"}
    return {
        "plugin": plugin_name,
        "outcome": await update_backend_child(manager, parent_task_id, plugin_name),
    }


async def process_update_all_backends_async(
    manager: PluginManagerRuntimeProtocol,
    command: UpdateAllPluginBackendsCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    registry = manager.dependencies.infrastructure.task_registry
    helpers = manager.dependencies.infrastructure.task_helpers
    reply_channel, context = command.reply_channel, command.context
    try:
        async with manager.dependencies.infrastructure.lifecycle.lifecycle_scope(
            service_name="Plugin manager",
            task_type="update_all_backends",
            user_id=resolve_user_id_from_context(context),
            task_id=resolve_task_id_from_context(context),
            context=context,
        ) as (_, task_id):
            try:
                manager.require_online_mode("update all plugin backends")
                parent = await registry.get(task_id, force_refresh=True)
                if parent is None or parent.status.is_terminal():
                    raise StateError("Bulk backend update parent is unavailable.")
                children = parent.metadata.get("backend_update_children", {})
                if not isinstance(children, dict):
                    raise StateError("Bulk backend update child metadata is invalid.")
                candidates: set[str] = set(children)
                for plugin in await manager.list_plugins():
                    capabilities = plugin.get("capabilities")
                    name = plugin.get("name")
                    if (
                        isinstance(name, str)
                        and name
                        and isinstance(capabilities, dict)
                        and capabilities.get("supports_backend_installation") is True
                        and plugin.get("installed") is True
                    ):
                        candidates.add(name)
                if command.plugin_name is not None:
                    candidates.intersection_update((command.plugin_name,))
                outcomes: list[JSONValue] = []
                cooldown = False
                for index, plugin_name in enumerate(sorted(candidates)):
                    await send_progress_with_task(
                        reply_channel,
                        task_id,
                        int(index * 100 / len(candidates)),
                        f"Checking backend {plugin_name} ({index + 1}/{len(candidates)}).",
                        registry,
                        helpers.send_task_progress_event,
                    )
                    if cooldown and plugin_name not in children:
                        outcome: JSONDict = {
                            "plugin": plugin_name,
                            "outcome": "deferred",
                            "reason": "deferred",
                        }
                    else:
                        outcome = await _update_one_plugin(
                            manager,
                            plugin_name,
                            task_id,
                            has_reserved_child=plugin_name in children,
                        )
                    outcomes.append(outcome)
                    cooldown = cooldown or outcome.get("reason") == "deferred"
                incomplete = any(
                    isinstance(outcome, dict)
                    and outcome.get("outcome") in ("failed", "deferred", "cancelled")
                    for outcome in outcomes
                )
                if not outcomes:
                    message = "No installed plugin backends are eligible for this batch."
                elif incomplete:
                    message = "Backend update batch finished with failed or deferred work."
                elif all(
                    isinstance(outcome, dict) and outcome.get("outcome") == "current"
                    for outcome in outcomes
                ):
                    message = "All checked plugin backends are current."
                else:
                    message = "Backend update batch completed."
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=not incomplete,
                    message=message,
                    result={"outcomes": outcomes},
                    task_registry=registry,
                    send_task_complete_event_callable=helpers.send_task_complete_event,
                )
            except asyncio.CancelledError:
                await notify_operation_cancelled(
                    "Update of all plugin backends",
                    reply_channel,
                    task_id,
                    registry,
                    helpers.send_task_complete_event,
                )
                raise
            except BULK_FAILURES as exception:
                log_exception(
                    logger,
                    exception,
                    message="Backend update batch failed.",
                    operation=OPERATION,
                )
                await send_unexpected_error_completion_for_plugin_manager(
                    manager,
                    reply_channel,
                    task_id,
                    exception,
                )
    except TaskIDCollisionError as exception:
        await handle_plugin_manager_task_id_collision(manager, exception, reply_channel)
