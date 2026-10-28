"""SoAI - Automatic backend update eligibility and durable admission [backend/plugins/manager/backend_update_automatic.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
    UpdatePluginBackendCommand,
)
from core.events.types_system import ConfigReloadedEvent, SoAIMainStateChangedEvent
from core.events.types_tasks import TaskStatusChangedEvent
from core.mutations.dispatch_notification import notify_mutation_dispatch_requested
from core.mutations.identifiers import create_mutation_request_id
from core.mutations.identity_window import (
    MutationIdentityExpiredError,
    MutationIdentityTimeSkewError,
    validate_mutation_identity_window,
)
from core.plugins.backend_mutation_admission import build_backend_mutation_admission
from core.plugins.backend_update_records import BackendAutoAttempt, BackendUpdateRecord
from core.plugins.builtin_names import BUILTIN_PLUGIN_NAMES
from core.runtime.network_policy import is_offline_mode_enabled
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.errors import MutationAdmissionConflictError
from core.tasks.type_catalog import TASK_TYPE_BACKEND_UPDATE
from core.timing.epoch import epoch_ms
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.manager.backend_update_admission import (
    backend_update_admission_allowed,
    backend_update_runtime_idle,
)
from plugins.manager.backend_update_identity import capture_backend_update_identity
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

AUTOMATIC_BACKEND_UPDATE_OWNER = "plugin-backend-updates"

__all__ = (
    "admit_automatic_backend_update",
    "backend_update_availability",
    "automatic_backend_update_ready",
    "automatic_backend_update_enabled",
    "require_automatic_update_policy",
)


def automatic_backend_update_enabled(
    manager: PluginManagerRuntimeProtocol, plugin_name: str
) -> bool:
    return (
        plugin_name in BUILTIN_PLUGIN_NAMES
        and manager.dependencies.core.config.get_bool("PLUGINS.BACKEND_UPDATES.AUTO_UPDATE_BUILTIN")
        and not is_offline_mode_enabled(manager.dependencies.infrastructure.runtime_flags)
        and not manager.dependencies.infrastructure.runtime_health.repair_plane
        and not manager.dependencies.infrastructure.runtime_health.restart_pending.is_set()
        and not manager.lifecycle.disabled
        and not manager.lifecycle.shutdown_event.is_set()
    )


async def require_automatic_update_policy(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
    *,
    before_execution: bool,
) -> None:
    claim = command.mutation_claim
    if claim is None or claim.owner_id != AUTOMATIC_BACKEND_UPDATE_OWNER:
        return
    plugin_name = command.plugin_name
    record = await manager.dependencies.databases.plugins.get_backend_update(plugin_name)
    if (
        record is None
        or record.auto_attempt is None
        or record.auto_attempt.request_id != claim.request_id
    ):
        raise asyncio.CancelledError("Automatic backend update reservation was superseded.")
    attempt = record.auto_attempt
    if not automatic_backend_update_enabled(manager, plugin_name):
        raise asyncio.CancelledError("Automatic backend update was disabled.")
    identity = await capture_backend_update_identity(
        manager, plugin_name, require_loaded_hash=False
    )
    if identity != attempt.identity:
        raise asyncio.CancelledError("Automatic backend update identity was superseded.")
    if before_execution and not await backend_update_runtime_idle(
        manager, plugin_name, require_stopped=True
    ):
        raise asyncio.CancelledError("Automatic backend update is no longer safely stopped.")


async def admit_automatic_backend_update(
    manager: PluginManagerRuntimeProtocol,
    record: BackendUpdateRecord,
) -> bool:
    plugin_name = record.identity.plugin_name
    if not automatic_backend_update_enabled(manager, plugin_name):
        return False
    registry = manager.dependencies.infrastructure.task_registry
    database = manager.dependencies.databases.plugins
    needs_admission = True
    async with plugin_lifecycle_advisory_lock(manager, plugin_name):
        async with manager.lifecycle.bounded_plugin_lock_scope(
            plugin_name, timeout_seconds=30
        ) as admission:
            if not admission.acquired:
                return False
            current = await database.get_backend_update(plugin_name)
            if (
                current is None
                or current.status != "update_available"
                or current.identity != record.identity
            ):
                return False
            if not await backend_update_admission_allowed(
                manager, plugin_name, require_stopped=True
            ):
                return False
            async with (
                manager.dependencies.infrastructure.config_manager.plugin_config_mutation_scope(
                    plugin_name, operation="plugins.manager.backend_update_automatic"
                )
            ):
                identity = await capture_backend_update_identity(
                    manager, plugin_name, require_loaded_hash=False
                )
                if identity != current.identity:
                    return False
                attempt = current.auto_attempt
                if attempt is not None and attempt.identity.package_hash == identity.package_hash:
                    task = await registry.get(attempt.request_id, force_refresh=True)
                    if task is not None:
                        if task.status.is_terminal():
                            await database.set_backend_update_failure(
                                attempt, task.status == TaskStatus.FAILED
                            )
                            return False
                        needs_admission = False
                    else:
                        if attempt.identity != identity:
                            return False
                        try:
                            validate_mutation_identity_window(attempt.request_id, epoch_ms())
                        except (MutationIdentityExpiredError, MutationIdentityTimeSkewError):
                            return False
                else:
                    if await registry.database_tasks.has_unsettled_backend_update(plugin_name):
                        return False
                    attempt = BackendAutoAttempt(create_mutation_request_id(), identity)
                    if not await database.reserve_backend_update(current, attempt):
                        return False
    if needs_admission:
        try:
            await create_streaming_task(
                registry,
                TASK_TYPE_BACKEND_UPDATE,
                0,
                AUTOMATIC_BACKEND_UPDATE_OWNER,
                "system",
                task_id=attempt.request_id,
                cancellation_id=f"backend-update::{attempt.request_id}",
                progress_total=100,
                metadata={
                    "plugin_name": plugin_name,
                    "display_name": await manager.get_plugin_display_name(plugin_name),
                    "automatic": True,
                },
                mutation_admission=build_backend_mutation_admission(
                    request_id=attempt.request_id,
                    plugin_name=plugin_name,
                    operation_type="update_backend",
                    command_fields={"backend_variant_id": identity.backend_variant_id},
                ),
            )
        except MutationAdmissionConflictError:
            return False
    await notify_mutation_dispatch_requested(manager.dependencies.infrastructure.event_bus)
    terminal = await registry.wait_for_completion(attempt.request_id, timeout=7200)
    if terminal is None or not terminal.status.is_terminal():
        raise StateError("Automatic backend update has no terminal result.")
    await database.set_backend_update_failure(attempt, terminal.status == TaskStatus.FAILED)
    return True


async def automatic_backend_update_ready(
    manager: PluginManagerRuntimeProtocol, command: UpdatePluginBackendCommand
) -> bool:
    claim = command.mutation_claim
    if (
        claim is None
        or claim.owner_id != AUTOMATIC_BACKEND_UPDATE_OWNER
        or claim.execution_phase != "accepted"
    ):
        return True
    await require_automatic_update_policy(manager, command, before_execution=False)
    return await backend_update_admission_allowed(
        manager, command.plugin_name, require_stopped=True
    )


@asynccontextmanager
async def backend_update_availability(
    manager: PluginManagerRuntimeProtocol,
) -> AsyncGenerator[asyncio.Event]:
    wake = asyncio.Event()

    async def on_change(_event: Event) -> None:
        wake.set()

    event_bus = manager.dependencies.infrastructure.event_bus
    events = (
        PluginRuntimeStateChangedEvent,
        PluginInstallationStateChangedEvent,
        ConfigReloadedEvent,
        SoAIMainStateChangedEvent,
        TaskStatusChangedEvent,
    )
    for event_type in events:
        event_bus.subscribe(event_type, on_change)
    try:
        yield wake
    finally:
        for event_type in events:
            event_bus.unsubscribe(event_type, on_change)
