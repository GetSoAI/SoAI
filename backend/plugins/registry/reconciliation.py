"""SoAI - Plugin database and filesystem reconciliation [backend/plugins/registry/reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.collections.sets import compute_set_deltas
from core.errors.exceptions import NotFoundError, SecurityError, StateError, ValidationError
from core.events.types_plugins import DeletePluginCommand
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.runtime.request_context import create_system_context
from core.state.compatibility import IncompatibilityReason
from core.state.state_names import PLUGIN_STATE_ABSENT, PLUGIN_STATE_DELETING
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_PLUGIN_DELETE
from core.timing.monotonic import monotonic_ms
from core.types.json import is_json_dict
from plugins.hash_blocklist import (
    build_blocked_plugin_hash_error,
    get_blocked_plugin_hash_compatibility,
)
from plugins.loader.incompatibility import handle_incompatible_plugin
from plugins.loader.record_data import build_plugin_record_data
from plugins.manager.alias_map import update_alias_map
from plugins.manager.artifacts import purge_plugin_from_memory
from plugins.manifest.reader import read_plugin_manifests_from_disk
from plugins.package_audit import audit_plugin_package
from plugins.package_cache_gc import collect_plugin_package_caches
from plugins.path_safety import scan_for_plugin_files
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.registry.delete import process_delete_plugin_async
from plugins.registry.reconciled_catalog_state import finalize_reconciled_catalog_states
from plugins.registry.reconciliation_loading import (
    process_manifest_dependency_and_loading,
)
from plugins.registry.startup_concurrency import resolve_plugin_startup_concurrency
from plugins.state.compatibility import build_compatibility_info

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.package_audit import PluginPackageAudit

__all__ = ("reconcile_db_with_filesystem",)

LOGGER_NAME = "SoAI.plugins.registry.reconciliation"
OPERATION_PLUGIN_MANIFEST_EXTRACTION = "plugins.registry.reconciliation.extract_plugin_manifest"


async def remove_reserved_clone_targets(
    manager: PluginManagerRuntimeProtocol,
    active_plugin_names: set[str],
) -> None:
    reserved_targets = (
        await manager.dependencies.databases.plugins.clone_transactions.list_reserved_targets()
    )
    active_plugin_names.difference_update(reserved_targets)


async def _inspect_active_plugin_sources(
    manager: PluginManagerRuntimeProtocol,
    plugin_names: set[str],
) -> dict[str, PluginPackageAudit]:
    inspect_semaphore = asyncio.Semaphore(resolve_plugin_startup_concurrency(manager))
    audits: dict[str, PluginPackageAudit] = {}

    async def inspect_one(plugin_name: str) -> None:
        async with inspect_semaphore:
            package_audit = await audit_plugin_package(
                manager,
                plugin_name,
                enforce_import_scan=False,
                enforce_hash_policy=False,
            )
            audits[plugin_name] = package_audit

    inspect_tasks = [inspect_one(plugin_name) for plugin_name in sorted(plugin_names)]
    await asyncio.gather(*inspect_tasks, return_exceptions=False)
    return audits


async def reconcile_db_with_filesystem(
    manager: PluginManagerRuntimeProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.debug(
        "Reconciling plugins: checking filesystem against database and loading all available plugins...",
    )
    step_started_ms = monotonic_ms()
    active_on_disk_names: set[str] = set()
    for plugin_info in await scan_for_plugin_files(manager.paths.plugin_directory):
        if not is_json_dict(plugin_info):
            continue
        plugin_name_value = plugin_info.get("plugin_name")
        if isinstance(plugin_name_value, str) and plugin_name_value:
            active_on_disk_names.add(plugin_name_value)
    await remove_reserved_clone_targets(manager, active_on_disk_names)
    logger.debug(
        "Plugin reconciliation filesystem scan completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    present_on_disk_names = set(active_on_disk_names)
    step_started_ms = monotonic_ms()
    all_db_records: dict[str, JSONDict] = {}
    for plugin in await manager.dependencies.databases.plugins.get_all_plugins():
        if not is_json_dict(plugin):
            continue
        plugin_name_value = plugin.get("plugin_name")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            continue
        all_db_records[plugin_name_value] = plugin
    logger.debug(
        "Plugin reconciliation database record load completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    for plugin_name, record in all_db_records.items():
        if not isinstance(record, dict):
            continue
        state_value = record.get("state")
        state_str = state_value if isinstance(state_value, str) else None
        context = create_system_context(f"reconcile_{state_str.lower() if state_str else 'none'}")
        if state_str == PLUGIN_STATE_DELETING:
            logger.warning(
                "Reconciliation: Found plugin '%s' in DELETING state. Re-initiating deletion process.",
                plugin_name,
            )
            registry = manager.dependencies.infrastructure.task_registry
            task_helpers = manager.dependencies.infrastructure.task_helpers
            task, reply_queue = await task_helpers.create_streaming_task(
                registry,
                task_type=TASK_TYPE_PLUGIN_DELETE,
                user_id=0,
                owner_id="system",
                owner_type="system",
                cancellation_id=context.cancellation_id,
                initial_status=TaskStatus.WORKING,
                progress_total=100,
                metadata={
                    "operation": "reconcile_delete_plugin",
                    "plugin_name": plugin_name,
                },
            )
            context.task_id = task.task_id
            cmd = DeletePluginCommand(
                plugin_name=plugin_name,
                delete_models=True,
                reply_channel=reply_queue,
                context=context,
            )
            lifecycle = manager.dependencies.infrastructure.lifecycle
            _ = task_helpers.spawn_tracked_task(
                process_delete_plugin_async(manager, cmd),
                logger=logger,
                name=f"plugin-delete-{cmd.plugin_name}",
                cancellation_binder=lifecycle.cancellation_binder,
                cancellation_id=context.cancellation_id,
                owner="plugin_reconciliation_delete",
                finalizer_tracker=lifecycle.finalizer_tracker,
            )
    blocked_plugins: set[str] = set()
    package_audits: dict[str, PluginPackageAudit] = {}
    try:
        step_started_ms = monotonic_ms()
        package_audits = await _inspect_active_plugin_sources(manager, active_on_disk_names)
        logger.debug(
            "Plugin reconciliation source inspection completed in %sms.",
            monotonic_ms() - step_started_ms,
        )
    except (NotFoundError, SecurityError, StateError, ValidationError):
        package_audits = {}
    for plugin_name in sorted(active_on_disk_names):
        try:
            package_audit = package_audits.get(plugin_name)
            if package_audit is None:
                package_audit = await audit_plugin_package(
                    manager,
                    plugin_name,
                    enforce_import_scan=False,
                    enforce_hash_policy=False,
                )
                package_audits[plugin_name] = package_audit
        except (NotFoundError, SecurityError, StateError, ValidationError):
            compatibility = build_compatibility_info(
                IncompatibilityReason.BROKEN_PLUGIN,
                f"Could not calculate plugin hash for '{plugin_name}'. The plugin will not be loaded.",
                {"plugin_name": plugin_name},
                False,
            )
            await handle_incompatible_plugin(
                manager,
                PluginIncompatibleError(plugin_name, compatibility, plugin_class_name=None),
                plugin_data_override=await build_plugin_record_data(
                    manager,
                    plugin_name,
                    operation=OPERATION_PLUGIN_MANIFEST_EXTRACTION,
                    error_message="Reconciliation: Failed to extract plugin manifest (non-critical).",
                ),
            )
            blocked_plugins.add(plugin_name)
            continue
        plugin_file_hash = package_audit.content.archive_hash
        if get_blocked_plugin_hash_compatibility(plugin_file_hash) is None:
            continue
        blocked_plugins.add(plugin_name)
        logger.warning(
            "Reconciliation: blocking plugin '%s' due to local hash policy (sha256=%s).",
            plugin_name,
            plugin_file_hash,
        )
        await handle_incompatible_plugin(
            manager,
            build_blocked_plugin_hash_error(plugin_name, plugin_file_hash),
            plugin_data_override=await build_plugin_record_data(
                manager,
                plugin_name,
                package_audit=package_audit,
                operation=OPERATION_PLUGIN_MANIFEST_EXTRACTION,
                error_message="Reconciliation: Failed to extract plugin manifest (non-critical).",
            ),
        )
    if blocked_plugins:
        active_on_disk_names -= blocked_plugins
    step_started_ms = monotonic_ms()
    loaded_manifests = await read_plugin_manifests_from_disk(
        manager,
        sorted(active_on_disk_names),
        package_audits=package_audits,
        concurrency_limit=resolve_plugin_startup_concurrency(manager),
    )
    logger.debug(
        "Plugin reconciliation manifest load completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    active_on_disk = set(loaded_manifests.keys())
    uninspected_plugins = sorted(active_on_disk_names - active_on_disk)
    for plugin_name in uninspected_plugins:
        compatibility = build_compatibility_info(
            IncompatibilityReason.BROKEN_PLUGIN,
            f"Could not inspect plugin '{plugin_name}' manifest. The plugin will not be loaded.",
            {"plugin_name": plugin_name},
            False,
        )
        await handle_incompatible_plugin(
            manager,
            PluginIncompatibleError(plugin_name, compatibility, plugin_class_name=None),
            plugin_data_override=await build_plugin_record_data(
                manager,
                plugin_name,
                operation=OPERATION_PLUGIN_MANIFEST_EXTRACTION,
                error_message="Reconciliation: Failed to extract plugin manifest (non-critical).",
            ),
        )
    step_started_ms = monotonic_ms()
    await process_manifest_dependency_and_loading(
        manager,
        loaded_manifests,
        active_on_disk=active_on_disk,
        package_audits=package_audits,
    )
    await finalize_reconciled_catalog_states(manager, active_on_disk)
    logger.debug(
        "Plugin reconciliation manifest processing completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    expected_present: set[str] = set()
    for name, record in all_db_records.items():
        if isinstance(record, dict) and isinstance(name, str):
            record_state = record.get("state")
            if record_state != PLUGIN_STATE_ABSENT:
                expected_present.add(name)
    plugins_to_mark_absent, _ = compute_set_deltas(expected_present, present_on_disk_names)
    if plugins_to_mark_absent:
        logger.debug(
            "Reconciliation: Marking missing plugins as ABSENT: %s",
            list(plugins_to_mark_absent),
        )
        await manager.dependencies.databases.plugins.mark_as_absent(list(plugins_to_mark_absent))
        for plugin_name in plugins_to_mark_absent:
            async with manager.dependencies.infrastructure.lifecycle.plugin_lock_scope(plugin_name):
                await purge_plugin_from_memory(manager, plugin_name)
    step_started_ms = monotonic_ms()
    await update_alias_map(manager)
    await collect_plugin_package_caches(
        manager,
        {
            plugin_name: package_audit.content.archive_hash
            for plugin_name, package_audit in package_audits.items()
        },
    )
    logger.debug(
        "Plugin reconciliation alias map update completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    logger.debug("Plugin reconciliation and initial loading complete.")
