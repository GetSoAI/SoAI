"""SoAI - Plugin reconciliation dependency and loading operations [backend/plugins/registry/reconciliation_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.runtime.soai_identifiers import create_system_id
from core.state.state_names import PLUGIN_STATE_LOAD_ERROR, PLUGIN_STATE_STOPPED
from plugins.loader.incompatibility import (
    handle_incompatible_plugin,
    handle_plugin_compatibility_failure,
    propagate_incompatibility_to_dependents,
)
from plugins.loader.loading import PLUGIN_LOAD_FAILURE_EXCEPTIONS
from plugins.loader.preflight import perform_plugin_preflight_checks
from plugins.loader.record_data import build_plugin_record_data
from plugins.manager.configuration import reconcile_plugin_configuration
from plugins.manifest.dependency_assessment import (
    build_missing_dependency_compatibility,
    build_missing_dependency_plugin_data,
)
from plugins.manifest.dependency_index import build_plugin_dependency_index
from plugins.registry.dependency_cycles import get_cyclic_plugins
from plugins.registry.startup_concurrency import resolve_plugin_startup_concurrency
from plugins.state.load_order import get_plugin_load_order
from plugins.state.transition_publication import transition_plugin_state_and_wait

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("process_manifest_dependency_and_loading",)

LOGGER_NAME = "SoAI.plugins.registry.reconciliation_loading"
OPERATION = "plugin_manager.reconciliation"


async def _recover_stale_catalog_load_error(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    existing_record: JSONDict | None,
) -> None:
    persisted_state = existing_record.get("state") if existing_record else None
    if persisted_state != PLUGIN_STATE_LOAD_ERROR:
        return
    await transition_plugin_state_and_wait(
        manager,
        plugin_name,
        PLUGIN_STATE_STOPPED,
        "Catalog reconciliation succeeded after a previous plugin load failure.",
    )


async def process_manifest_dependency_and_loading(
    manager: PluginManagerRuntimeProtocol,
    loaded_manifests: dict[str, JSONDict],
    *,
    active_on_disk: set[str],
    package_audits: dict[str, PluginPackageAudit] | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    dependency_index = build_plugin_dependency_index(loaded_manifests)
    incompatible_plugins = set(dependency_index.missing_dependencies_by_plugin.keys())
    for plugin_name in dependency_index.missing_dependencies_by_plugin:
        assessment = dependency_index.assessments[plugin_name]
        compatibility = build_missing_dependency_compatibility(assessment)
        await handle_plugin_compatibility_failure(
            manager,
            plugin_name,
            compatibility,
            plugin_class_name=assessment.class_name,
            plugin_data_override=build_missing_dependency_plugin_data(assessment),
        )
    incompatible_plugins = await propagate_incompatibility_to_dependents(
        manager,
        incompatible_plugins,
        dependency_index.class_names_by_plugin,
        dependency_index.declared_dependencies_by_plugin,
    )
    plugin_graph = dependency_index.graph_excluding(incompatible_plugins)
    try:
        load_order = get_plugin_load_order(plugin_graph)
    except ValidationError as exception:
        error_message = str(exception)
        log_exception(
            logger,
            exception,
            message="Could not determine plugin load order due to dependency issue. Some plugins may not load.",
            operation=OPERATION,
            level="critical",
        )
        cyclic_plugins = get_cyclic_plugins(error_message, plugin_graph)
        if cyclic_plugins:
            logger.warning(
                "Excluding plugins from load due to dependency issues: %s",
                sorted(cyclic_plugins),
            )
        load_order = [
            plugin
            for plugin in sorted(active_on_disk)
            if plugin in plugin_graph and plugin not in cyclic_plugins
        ]
    await _persist_catalog_for_order(
        manager,
        loaded_manifests,
        plugin_graph,
        load_order,
        package_audits=package_audits or {},
    )


async def _persist_catalog_for_order(
    manager: PluginManagerRuntimeProtocol,
    loaded_manifests: dict[str, JSONDict],
    plugin_graph: dict[str, set[str]],
    load_order: list[str],
    *,
    package_audits: dict[str, PluginPackageAudit],
) -> None:
    if not load_order:
        return
    logger = get_logger(LOGGER_NAME)
    plugin_startup_concurrency = resolve_plugin_startup_concurrency(manager)
    completion_events = {plugin_name: asyncio.Event() for plugin_name in load_order}
    results: dict[str, bool] = {}
    results_lock = asyncio.Lock()
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    for plugin_name in load_order:
        queue.put_nowait(plugin_name)
    worker_count = min(max(1, plugin_startup_concurrency), max(1, len(load_order)))
    for _index in range(worker_count):
        queue.put_nowait(None)

    async def _persist_with_dependencies(target: str) -> bool:
        local_logger = get_logger(LOGGER_NAME)
        try:
            dependencies = plugin_graph.get(target, set())
            if dependencies:
                for dependency in dependencies:
                    if dependency in completion_events and dependency != target:
                        await completion_events[dependency].wait()
                async with results_lock:
                    dependency_failed = any(
                        results.get(dependency) is False
                        or (dependency in completion_events and dependency not in results)
                        for dependency in dependencies
                    )
                if dependency_failed:
                    local_logger.warning(
                        "Reconciliation: Skipping plugin '%s' because one or more dependencies failed catalog validation.",
                        target,
                    )
                    return False
            if target not in loaded_manifests:
                local_logger.warning(
                    "Reconciliation: Plugin class not found for '%s'. Skipping catalog record.",
                    target,
                )
                return False
            local_logger.debug(
                "Reconciliation: Cataloging plugin '%s' in dependency order (concurrency=%s)...",
                target,
                plugin_startup_concurrency,
            )
            preflight_result = await perform_plugin_preflight_checks(
                manager,
                target,
                package_audit=package_audits.get(target),
                manifest=loaded_manifests.get(target),
                dependency_manifests=loaded_manifests,
            )
            plugin_data = await build_plugin_record_data(
                manager,
                target,
                plugin_data_override=preflight_result.manifest,
                package_audit=preflight_result.package_audit,
            )
            await manager.dependencies.databases.plugins.add_or_update_plugin(
                plugin_data,
                incompatibility=preflight_result.compatibility,
            )
            if preflight_result.compatibility.reason is None:
                await _recover_stale_catalog_load_error(
                    manager,
                    target,
                    preflight_result.existing_record,
                )
            default_configuration = plugin_data.get("default_configuration")
            parameter_schema = plugin_data.get("parameter_schema")
            if isinstance(default_configuration, dict):
                _config, success = await reconcile_plugin_configuration(
                    manager,
                    target,
                    default_configuration,
                    parameter_schema=(
                        parameter_schema if isinstance(parameter_schema, dict) else {}
                    ),
                )
                if not success:
                    return False
            if isinstance(parameter_schema, dict) and parameter_schema:
                await manager.dependencies.models.parameter_manager.register_plugin_parameters(
                    target,
                    parameter_schema,
                )
            return True
        except PluginIncompatibleError as exception:
            manifest = loaded_manifests.get(target)
            if manifest is None:
                log_exception(
                    local_logger,
                    exception,
                    message="Reconciliation plugin preflight failed without manifest metadata; incompatibility could not be persisted.",
                    operation=OPERATION,
                    details={"plugin_name": target},
                    level="warning",
                )
                return False
            await handle_incompatible_plugin(
                manager,
                exception,
                plugin_data_override=manifest,
            )
            return False
        except PLUGIN_LOAD_FAILURE_EXCEPTIONS as exception:
            log_exception(
                local_logger,
                exception,
                message="Reconciliation plugin cataloging failed.",
                operation=OPERATION,
                details={"plugin_name": target},
                level="warning",
            )
            return False

    async def _worker() -> None:
        while True:
            plugin_name = await queue.get()
            if plugin_name is None:
                return
            try:
                result = await _persist_with_dependencies(plugin_name)
                async with results_lock:
                    results[plugin_name] = result
            finally:
                completion_events[plugin_name].set()

    lifecycle = manager.dependencies.infrastructure.lifecycle
    worker_tasks = [
        manager.dependencies.infrastructure.task_helpers.spawn_tracked_task(
            _worker(),
            name=f"plugin-catalog-reconcile-worker-{index}",
            logger=logger,
            cancellation_binder=lifecycle.cancellation_binder,
            cancellation_id=create_system_id(
                subsystem="plugin_manager_catalog_reconcile",
                owner=str(index),
                include_random_suffix=True,
            ),
            owner="plugin_catalog_reconcile",
            finalizer_tracker=lifecycle.finalizer_tracker,
        )
        for index in range(worker_count)
    ]
    worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
    for worker_result in worker_results:
        if isinstance(worker_result, asyncio.CancelledError):
            raise worker_result
        if isinstance(worker_result, Exception):
            log_exception(
                logger,
                worker_result,
                message="Reconciliation plugin catalog worker failed unexpectedly.",
                operation=OPERATION,
                level="warning",
            )
