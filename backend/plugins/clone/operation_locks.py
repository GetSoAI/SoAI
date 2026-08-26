"""SoAI - Cross-process and local clone operation locks [backend/plugins/clone/operation_locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.errors.exceptions import ValidationError
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("clone_operation_locks",)


@asynccontextmanager
async def clone_operation_locks(
    manager: PluginManagerRuntimeProtocol,
    plugin_names: tuple[str, ...],
    *,
    mutation_task_id: str | None = None,
    mutation_fencing_token: int | None = None,
) -> AsyncGenerator[None]:
    ordered_names = tuple(sorted(set(plugin_names)))
    if len(ordered_names) == 1:
        (first_name,) = ordered_names
        second_name = None
    elif len(ordered_names) == 2:
        first_name, second_name = ordered_names
    else:
        raise ValidationError("Clone operation locks require one or two plugin identities.")
    lifecycle = manager.dependencies.infrastructure.lifecycle
    async with plugin_lifecycle_advisory_lock(
        manager,
        first_name,
        mutation_task_id=mutation_task_id,
        mutation_fencing_token=mutation_fencing_token,
    ):
        async with lifecycle.plugin_lock_scope(first_name):
            if second_name is None:
                yield
                return
            async with plugin_lifecycle_advisory_lock(
                manager,
                second_name,
                mutation_task_id=mutation_task_id,
                mutation_fencing_token=mutation_fencing_token,
            ):
                async with lifecycle.plugin_lock_scope(second_name):
                    yield
