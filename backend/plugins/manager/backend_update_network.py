"""SoAI - Cross-process backend network exclusion and admission [backend/plugins/manager/backend_update_network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import RateLimitError, StateError
from core.files.locking import async_guarded_file_lock
from core.filesystem.path_coercion import normalize_filesystem_path
from core.plugins.backend_update_records import BACKEND_UPDATE_CONTAINMENT_REQUIRED
from core.runtime.soai_identifiers import create_system_id
from core.state.state_names import PLUGIN_STATE_BACKEND_UPDATING, PLUGIN_STATE_UPDATE_ERROR
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.timing.epoch import epoch_ms
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.manager.backend_update_containment import contain_backend_update_worker
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
from plugins.state.transition_publication import transition_plugin_state_and_wait

__all__ = ("backend_update_network_scope",)


@asynccontextmanager
async def backend_update_network_scope(
    manager: PluginManagerRuntimeProtocol,
    *,
    mutation_task_id: str | None = None,
) -> AsyncGenerator[None]:
    directory = os.path.join(manager.paths.plugin_directory, ".locks")
    await run_joined_thread_call(
        os.makedirs,
        normalize_filesystem_path(directory),
        0o700,
        True,
        task_name="backend-update-lock-directory",
    )
    async with async_guarded_file_lock(
        os.path.join(directory, "backend-updates.network.lock"), timeout=INTERACTIVE_TIMEOUT_SEC
    ):
        tasks = manager.dependencies.infrastructure.task_registry.database_tasks
        for recovery in await tasks.query_recovery_required_admissions(
            operation_type="plugin_backend_update"
        ):
            if recovery.execution_phase not in {
                "accepted",
                "execution_started",
                "callback_succeeded",
                "verified",
                "contained_failure",
                "recovery_required",
            }:
                raise StateError("Backend update recovery checkpoint is unsupported.")
            async with plugin_lifecycle_advisory_lock(manager, recovery.target_identity):
                async with serialized_plugin_load_scope(manager, recovery.target_identity):
                    await cancellation_cleanup(
                        contain_backend_update_worker(manager, recovery.target_identity)
                    )
                    state = await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
                        recovery.target_identity
                    )
                    if state == PLUGIN_STATE_BACKEND_UPDATING:
                        await transition_plugin_state_and_wait(
                            manager,
                            recovery.target_identity,
                            PLUGIN_STATE_UPDATE_ERROR,
                            "Interrupted backend update was contained; manual repair is required.",
                        )
                    if not await cancellation_cleanup(
                        tasks.release_backend_update_recovery(
                            recovery.request_id, recovery.target_identity, now_ms=epoch_ms()
                        )
                    ):
                        raise StateError("Backend update recovery could not be released safely.")
        if await tasks.has_unsettled_backend_update(
            None,
            excluded_task_id=mutation_task_id,
        ):
            raise StateError("Backend update recovery must complete before another operation.")
        database = manager.dependencies.databases.plugins
        for record in (await database.get_backend_updates()).values():
            if record.failure_code != BACKEND_UPDATE_CONTAINMENT_REQUIRED:
                continue
            plugin_name = record.identity.plugin_name
            async with plugin_lifecycle_advisory_lock(manager, plugin_name):
                async with serialized_plugin_load_scope(manager, plugin_name):
                    await cancellation_cleanup(contain_backend_update_worker(manager, plugin_name))
                    pending = replace(
                        record,
                        status="check_pending",
                        failure_code=None,
                        current_version=None,
                        latest_version=None,
                        checked_at_ms=None,
                        check_id=create_system_id(
                            subsystem="backend-update", include_random_suffix=True
                        ),
                    )
                    if not await cancellation_cleanup(
                        database.commit_backend_update(record, pending)
                    ):
                        raise StateError("Backend containment recovery ownership changed.")
                    manager.state.catalog.backend_update_publication_pending = True
                    manager.state.catalog.backend_update_wake.set()
        if mutation_task_id is not None:
            cooldown = await manager.dependencies.databases.plugins.get_backend_update_cooldown()
            if cooldown is not None and cooldown > epoch_ms():
                raise RateLimitError(
                    "Backend updates are temporarily deferred by the shared network cooldown."
                )
        yield
