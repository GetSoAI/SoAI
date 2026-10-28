"""SoAI - Targeted plugin backend release checks [backend/plugins/manager/backend_update_checks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from filelock import Timeout

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.errors.backend_lifecycle import PluginLifecycleLockContentionError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    BackendUpdateContainmentError,
    ServiceUnavailableError,
    SoAIError,
    SoAITimeoutError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.backend_update_records import BackendUpdateRecord
from core.plugins.backend_update_results import (
    BackendUpdateResult,
    backend_update_error,
    normalize_backend_update_result,
)
from core.plugins.persistent_runtime_truth import get_plugin_status_payload
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.network_policy import require_online_mode
from core.runtime.soai_identifiers import create_system_id
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.manager.backend_update_admission import backend_update_admission_allowed
from plugins.manager.backend_update_containment import (
    contain_backend_update_worker,
    record_backend_update_containment_failure,
)
from plugins.manager.backend_update_identity import (
    backend_configuration_digest,
    capture_backend_update_identity,
)
from plugins.manager.backend_update_network import backend_update_network_scope
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.manager.compatibility import ensure_plugin_compatible
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

if TYPE_CHECKING:
    from core.plugins.backend_update_records import BackendUpdateStatus

__all__ = (
    "check_backend_update",
    "check_instance_backend_update",
)

OPERATION = "plugins.manager.backend_update_checks"
CHECK_TIMEOUT_SECONDS = 120.0
CHECK_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, SoAIError, RuntimeError)
CHECK_ADMISSION_FAILURES: tuple[type[Exception], ...] = (Timeout, *CHECK_FAILURES)


async def _read_backend_update_callback(
    manager: PluginManagerRuntimeProtocol,
    instance: PluginInstanceProtocol,
    configuration_hash: str | None,
) -> BackendUpdateResult:
    if not supports_plugin_capability_from_instance(instance, "SUPPORTS_BACKEND_INSTALLATION"):
        return backend_update_error("not_implemented", "Update check not supported.")
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            if supports_plugin_capability_from_instance(instance, "SUPPORTS_CONFIGURATION"):
                configuration = await instance.refresh_runtime_configuration()
                if backend_configuration_digest(configuration) != configuration_hash:
                    return backend_update_error(
                        "superseded", "Backend configuration changed; check deferred."
                    )
            status = await get_plugin_status_payload(
                instance, operation=OPERATION, logger=manager.logger, raise_on_error=True
            )
            installed = status.get("installed")
            if not isinstance(installed, bool) or status.get("error") is not None:
                return backend_update_error(
                    "invalid_response", "Backend installation status is unavailable."
                )
            if not installed:
                return normalize_backend_update_result(
                    {"update_available": False, "installed": False}, installed=False
                )
            return normalize_backend_update_result(
                await instance.check_for_backend_update(), installed=True
            )
    except (
        asyncio.CancelledError,
        TimeoutError,
        SoAITimeoutError,
        ServiceUnavailableError,
    ) as exception:
        try:
            await cancellation_cleanup(contain_backend_update_worker(manager, instance.plugin_name))
        except CHECK_FAILURES as containment_error:
            await cancellation_cleanup(
                record_backend_update_containment_failure(manager, instance.plugin_name)
            )
            raise BackendUpdateContainmentError(
                "Backend check worker containment failed."
            ) from containment_error
        if isinstance(exception, asyncio.CancelledError):
            raise
        log_exception(
            manager.logger,
            exception,
            message="Backend update check interrupted; worker containment completed.",
            operation=OPERATION,
            details={"plugin_name": instance.plugin_name},
            level="warning",
        )
        return backend_update_error("server_error", "Update check could not complete.")
    except CHECK_FAILURES as exception:
        log_exception(
            manager.logger,
            exception,
            message="Plugin backend update check failed.",
            operation=OPERATION,
            details={"plugin_name": instance.plugin_name},
            level="warning",
        )
        return backend_update_error("server_error", "Update check failed.")


async def _commit_check_result(
    manager: PluginManagerRuntimeProtocol,
    expected: BackendUpdateRecord,
    updated: BackendUpdateRecord,
) -> bool:
    database = manager.dependencies.databases.plugins
    if not await database.commit_backend_update(expected, updated):
        return False
    manager.state.catalog.backend_update_publication_pending = True
    manager.state.catalog.backend_update_wake.set()
    if updated.failure_code == "server_error":
        await database.extend_backend_update_cooldown(epoch_ms() + 300000)
    return True


async def check_instance_backend_update(
    manager: PluginManagerRuntimeProtocol,
    instance: PluginInstanceProtocol,
    *,
    previous_check_id: str | None = None,
    refresh: bool = True,
) -> BackendUpdateResult:
    database = manager.dependencies.databases.plugins
    config_manager = manager.dependencies.infrastructure.config_manager
    async with config_manager.plugin_config_mutation_scope(
        instance.plugin_name, operation=f"{OPERATION}.capture"
    ):
        identity = await capture_backend_update_identity(
            manager,
            instance.plugin_name,
            require_loaded_hash=True,
        )
        expected = await database.materialize_backend_update(identity)
        if expected.status in ("current", "update_available") and (
            not refresh or expected.check_id != previous_check_id
        ):
            return BackendUpdateResult(
                expected.status,
                {
                    "update_available": expected.status == "update_available",
                    "current_version": expected.current_version,
                    "latest_version": expected.latest_version,
                },
            )
        cooldown = await database.get_backend_update_cooldown()
        if cooldown is not None and cooldown > epoch_ms():
            return backend_update_error(
                "deferred", "Backend update checks are temporarily deferred."
            )
    result = await _read_backend_update_callback(manager, instance, identity.configuration_hash)
    async with config_manager.plugin_config_mutation_scope(
        instance.plugin_name, operation=f"{OPERATION}.commit"
    ):
        latest_identity = await capture_backend_update_identity(
            manager,
            instance.plugin_name,
            require_loaded_hash=result.status in {"current", "update_available"},
        )
        if latest_identity != identity:
            await database.materialize_backend_update(latest_identity)
            return backend_update_error("superseded", "Backend identity changed; check deferred.")
        succeeded = result.status in {"current", "update_available"}
        failure_code = None
        if not succeeded:
            error = result.payload.get("error")
            failure_code = (
                coerce_optional_trimmed_str(error.get("code"))
                if isinstance(error, dict)
                else "backend_absent"
            )
        stored_status: BackendUpdateStatus = "check_failed"
        if result.status in ("current", "update_available"):
            stored_status = result.status
        updated = replace(
            expected,
            status=stored_status,
            check_id=create_system_id(subsystem="backend-update", include_random_suffix=True),
            current_version=(
                coerce_optional_trimmed_str(result.payload.get("current_version"))
                if succeeded
                else expected.current_version
            ),
            latest_version=(
                coerce_optional_trimmed_str(result.payload.get("latest_version"))
                if succeeded
                else expected.latest_version
            ),
            checked_at_ms=epoch_ms() if succeeded else expected.checked_at_ms,
            failure_code=failure_code,
        )
        if not await cancellation_cleanup(_commit_check_result(manager, expected, updated)):
            return backend_update_error("superseded", "Backend update check was superseded.")
    return result


async def check_backend_update(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    refresh: bool = True,
) -> JSONDict:
    plugin_name = require_portable_plugin_identifier(plugin_name, field_name="plugin_name")
    manager.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    require_online_mode(
        manager.dependencies.infrastructure.runtime_flags, source="plugin backend update check"
    )
    try:
        await ensure_plugin_compatible(manager, plugin_name)
        previous = await manager.dependencies.databases.plugins.get_backend_update(plugin_name)
        async with backend_update_network_scope(manager):
            async with plugin_lifecycle_advisory_lock(manager, plugin_name):
                async with manager.lifecycle.bounded_plugin_lock_scope(
                    plugin_name, timeout_seconds=30
                ) as lock_result:
                    if not lock_result.acquired:
                        return backend_update_error(
                            "locked", "Backend update check is deferred."
                        ).payload
                    if not await backend_update_admission_allowed(
                        manager, plugin_name, require_stopped=False
                    ):
                        return backend_update_error(
                            "locked", "Backend update check is deferred in the current state."
                        ).payload
                    release_after_check = await manager.get_plugin_instance(plugin_name) is None
                    try:
                        instance = await manager.require_loaded_plugin(
                            plugin_name, auto_load=True, already_serialized=True
                        )
                        return (
                            await check_instance_backend_update(
                                manager,
                                instance,
                                previous_check_id=previous.check_id if previous else None,
                                refresh=refresh,
                            )
                        ).payload
                    finally:
                        if release_after_check:
                            await cancellation_cleanup(
                                manager.release_discovery_plugin_instance(plugin_name)
                            )
    except PluginLifecycleLockContentionError:
        return backend_update_error("locked", "Backend update check is deferred.").payload
    except CHECK_ADMISSION_FAILURES as exception:
        log_exception(
            manager.logger,
            exception,
            message="Plugin backend update check could not complete.",
            operation=OPERATION,
            details={"plugin_name": plugin_name},
            level="warning",
        )
        return backend_update_error(
            "server_error", "Update check could not complete. Try again later."
        ).payload
