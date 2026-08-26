"""SoAI - Cross-process plugin lifecycle lock [backend/plugins/lifecycle_advisory_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from filelock import Timeout

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import ServiceUnavailableError, StateError
from core.files.locking import async_guarded_file_lock
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import require_positive_int_strict
from core.validation.strings import coerce_optional_trimmed_str
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = (
    "plugin_lifecycle_advisory_lock",
    "resolve_plugin_lifecycle_lock_path",
)

LOCK_ACQUISITION_TIMEOUT_SECONDS = 30
LOCK_ACQUISITION_DEADLINE_SECONDS = 30


def resolve_plugin_lifecycle_lock_path(
    plugin_directory: str,
    plugin_name: str,
) -> str:
    normalized_name = require_portable_plugin_identifier(
        plugin_name,
        field_name="plugin_name",
    )
    return os.path.join(plugin_directory, ".locks", f"{normalized_name}.lifecycle.lock")


async def _mutation_claim_is_current(
    manager: PluginManagerRuntimeProtocol,
    task_id: str,
    fencing_token: int,
) -> bool:
    return await manager.dependencies.infrastructure.task_registry.database_tasks.validate_mutation_claim(
        task_id,
        fencing_token,
        now_ms=epoch_ms(),
    )


@asynccontextmanager
async def plugin_lifecycle_advisory_lock(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    mutation_task_id: str | None = None,
    mutation_fencing_token: int | None = None,
) -> AsyncGenerator[None]:
    normalized_name = require_portable_plugin_identifier(
        plugin_name,
        field_name="plugin_name",
    )
    normalized_fencing_token = (
        require_positive_int_strict(
            mutation_fencing_token,
            error_message="Plugin lifecycle mutation lock requires a positive fencing token.",
        )
        if mutation_fencing_token is not None
        else None
    )
    normalized_task_id = (
        coerce_optional_trimmed_str(mutation_task_id)
        if normalized_fencing_token is not None
        else None
    )
    if normalized_fencing_token is not None and normalized_task_id is None:
        raise StateError("Plugin lifecycle mutation lock requires a complete claim identity.")
    lock_directory = os.path.join(manager.paths.plugin_directory, ".locks")
    await uncancel_and_wait(
        asyncio.to_thread(os.makedirs, lock_directory, mode=0o700, exist_ok=True)
    )
    lock_path = resolve_plugin_lifecycle_lock_path(
        manager.paths.plugin_directory,
        normalized_name,
    )
    acquisition_deadline = deadline_after(LOCK_ACQUISITION_DEADLINE_SECONDS)
    while True:
        remaining_seconds = acquisition_deadline.remaining_seconds()
        if remaining_seconds <= 0.0:
            raise ServiceUnavailableError("Plugin lifecycle lock acquisition deadline expired.")
        entered = False
        try:
            async with async_guarded_file_lock(
                lock_path,
                timeout=min(LOCK_ACQUISITION_TIMEOUT_SECONDS, remaining_seconds),
            ):
                entered = True
                if (
                    normalized_task_id is not None
                    and normalized_fencing_token is not None
                    and not await _mutation_claim_is_current(
                        manager,
                        normalized_task_id,
                        normalized_fencing_token,
                    )
                ):
                    raise StateError("Plugin lifecycle mutation claim is no longer current.")
                yield
                return
        except Timeout as exception:
            if entered:
                raise
            if normalized_task_id is None or normalized_fencing_token is None:
                raise StateError("Plugin lifecycle lock acquisition timed out.") from exception
            if not await _mutation_claim_is_current(
                manager,
                normalized_task_id,
                normalized_fencing_token,
            ):
                raise StateError(
                    "Plugin lifecycle mutation claim is no longer current."
                ) from exception
            if acquisition_deadline.expired():
                raise ServiceUnavailableError(
                    "Plugin lifecycle lock acquisition deadline expired."
                ) from exception
