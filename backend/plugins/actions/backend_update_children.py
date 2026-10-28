"""SoAI - Admission and observation of sequential backend update children [backend/plugins/actions/backend_update_children.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.errors.exceptions import SoAITimeoutError, StateError
from core.mutations.dispatch_notification import notify_mutation_dispatch_requested
from core.mutations.identifiers import create_mutation_request_id
from core.plugins.backend_mutation_admission import build_backend_mutation_admission
from core.plugins.backend_update_child import BackendUpdateChild
from core.plugins.backend_variant_ids import AUTO_BACKEND_VARIANT_ID
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.errors import MutationAdmissionConflictError
from core.tasks.type_catalog import TASK_TYPE_BACKEND_UPDATE
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("update_backend_child",)


async def _cancel_and_join_child(
    manager: PluginManagerRuntimeProtocol,
    request_id: str,
) -> None:
    registry = manager.dependencies.infrastructure.task_registry
    child = await registry.get(request_id, force_refresh=True)
    if child is None or child.status.is_terminal():
        return
    await registry.cancellation_coordinator.cancel_scope(
        child.cancellation_id,
        "Bulk backend update was cancelled.",
    )
    terminal = await registry.wait_for_completion(child.task_id, timeout=120)
    if terminal is None or not terminal.status.is_terminal():
        raise StateError("Cancelled backend update child has not settled.")


async def update_backend_child(
    manager: PluginManagerRuntimeProtocol,
    parent_task_id: str,
    plugin_name: str,
) -> str:
    registry = manager.dependencies.infrastructure.task_registry
    parent = await registry.get(parent_task_id, force_refresh=True)
    if parent is None or parent.status.is_terminal():
        raise StateError("Bulk backend update parent is no longer active.")
    children = parent.metadata.get("backend_update_children", {})
    if not isinstance(children, dict):
        raise StateError("Bulk backend update child metadata is invalid.")
    variant_id = (
        AUTO_BACKEND_VARIANT_ID
        if plugin_name in children
        else await manager.snapshot_backend_variant_selection(plugin_name)
    )
    reservation = await registry.database_tasks.reserve_backend_update_child(
        parent_task_id,
        BackendUpdateChild(plugin_name, create_mutation_request_id(), variant_id),
    )
    child_id = reservation.request_id
    try:
        child, _ = await create_streaming_task(
            registry,
            TASK_TYPE_BACKEND_UPDATE,
            parent.user_id,
            parent.owner_id,
            parent.owner_type,
            task_id=child_id,
            cancellation_id=f"{parent.cancellation_id}::backend-update::{child_id}",
            progress_total=100,
            metadata={"plugin_name": plugin_name, "parent_task_id": parent_task_id},
            mutation_admission=build_backend_mutation_admission(
                request_id=child_id,
                plugin_name=plugin_name,
                operation_type="update_backend",
                command_fields={"backend_variant_id": reservation.backend_variant_id},
            ),
        )
        await notify_mutation_dispatch_requested(manager.dependencies.infrastructure.event_bus)
        terminal = await registry.wait_for_completion(child.task_id, timeout=7200)
        if terminal is None or not terminal.status.is_terminal():
            raise StateError("Backend update child has no authoritative terminal result.")
        if terminal.status == TaskStatus.COMPLETED:
            return "updated"
        return "cancelled" if terminal.status == TaskStatus.CANCELLED else "failed"
    except MutationAdmissionConflictError:
        return "deferred"
    except SoAITimeoutError:
        await cancellation_cleanup(_cancel_and_join_child(manager, child_id))
        raise
    except asyncio.CancelledError:
        await cancellation_cleanup(_cancel_and_join_child(manager, child_id))
        raise
