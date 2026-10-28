"""SoAI - Discovery provider execution and failure handling [backend/models/discovery/provider_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import (
    uncancel_then_cleanup,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.wait_race import wait_for_first_completed_tasks
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.models.provider_backing import is_provider_backed_model
from core.plugins.catalog_capabilities import plugin_record_supports_model_discovery
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_lifecycle import PluginDiscoveryOperationProtocol
from core.state.protocols import StateAggregatorProtocol
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
)
from core.state.state_transition_sets import PLUGIN_DISCOVERY_SKIP_STATES
from core.timing.monotonic import monotonic_ms
from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping
from core.validation.boolean_coercion import coerce_bool_with_recovery
from models.discovery.provider_bounded_execution import (
    DiscoveryPassCoordination,
    PluginCheckFailure,
    PluginCheckSuccess,
    PluginCheckUnchanged,
    ProviderCatalogDiscovery,
)

if TYPE_CHECKING:
    from models.discovery.provider_bounded_execution import PluginDiscoveryResult

__all__ = (
    "DiscoveryProviderContext",
    "discover_plugin_models",
    "run_plugin_precheck",
)

LOGGER_NAME = "SoAI.models.discovery.provider_execution"
OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_CHECK_PLUGIN = (
    "model_discovery.run_discovery_providers.check_plugin"
)
OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_DISCOVER_PLUGIN = (
    "model_discovery.run_discovery_providers.discover_plugin"
)
OPERATION_MODEL_DISCOVERY_RELEASE_DISCOVERY_PLUGIN = "model_discovery.release_discovery_plugin"
OPERATION_MODEL_DISCOVERY_PLUGIN_PERSISTENCE = "model_discovery.plugin_persistence"


SKIP_STATES = PLUGIN_DISCOVERY_SKIP_STATES


@dataclass(frozen=True, slots=True)
class DiscoveryProviderContext:
    plugin_manager: PluginManagerProtocol
    state_aggregator: StateAggregatorProtocol
    download_discovery_logged: set[str]
    disabled_discovery_logged: set[str]
    reuse_existing_models_for_unloaded_plugins: bool


async def _get_discovery_plugin_instance(
    plugin_manager: PluginManagerProtocol,
    plugin_name: str,
    logger: TraceLogger,
) -> PluginCheckSuccess | None:
    plugin_instance = await plugin_manager.get_plugin_instance(plugin_name)
    if plugin_instance is not None:
        return PluginCheckSuccess(
            plugin_name=plugin_name,
            instance=plugin_instance,
            loaded_for_discovery=False,
        )
    plugin_record = await plugin_manager.dependencies.databases.plugins.get_plugin_by_name(
        plugin_name,
    )
    if plugin_record is None or not plugin_record_supports_model_discovery(plugin_record):
        logger.debug(
            "Skipping plugin '%s' during discovery because its catalog record is not discovery-capable.",
            plugin_name,
        )
        return None
    plugin_instance = await plugin_manager.require_loaded_plugin(
        plugin_name,
        auto_load=True,
        already_serialized=True,
    )
    return PluginCheckSuccess(
        plugin_name=plugin_name,
        instance=plugin_instance,
        loaded_for_discovery=True,
    )


async def _release_discovery_plugin_instance(
    plugin_manager: PluginManagerProtocol,
    plugin_name: str,
    logger: TraceLogger,
) -> None:
    try:
        await plugin_manager.release_discovery_plugin_instance(plugin_name)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MODEL_DISCOVERY_RELEASE_DISCOVERY_PLUGIN,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to release short-lived discovery plugin instance.",
            operation=OPERATION_MODEL_DISCOVERY_RELEASE_DISCOVERY_PLUGIN,
            details={"plugin_name": plugin_name},
            level="warning",
        )


async def run_plugin_precheck(
    plugin_name: str,
    context: DiscoveryProviderContext,
) -> PluginCheckSuccess | PluginCheckFailure | PluginCheckUnchanged | None:
    logger = get_logger(LOGGER_NAME)
    plugin_manager = context.plugin_manager
    try:
        if await plugin_manager.is_model_download_in_progress(plugin_name):
            await plugin_manager.mark_discovery_pending_after_download(plugin_name)
            if plugin_name not in context.download_discovery_logged:
                logger.debug(
                    "Skipping discovery for '%s' during active model download.",
                    plugin_name,
                )
                context.download_discovery_logged.add(plugin_name)
            return None
        context.download_discovery_logged.discard(plugin_name)
        plugin_state = await context.state_aggregator.get_plugin_status(plugin_name)
        if plugin_state == ORCH_STATE_DISABLED:
            if plugin_name not in context.disabled_discovery_logged:
                logger.debug("Skipping discovery for disabled plugin '%s'.", plugin_name)
                context.disabled_discovery_logged.add(plugin_name)
            return None
        context.disabled_discovery_logged.discard(plugin_name)
        if context.reuse_existing_models_for_unloaded_plugins:
            plugin_instance = await plugin_manager.get_plugin_instance(plugin_name)
            if plugin_instance is None:
                plugin_record = (
                    await plugin_manager.dependencies.databases.plugins.get_plugin_by_name(
                        plugin_name,
                    )
                )
                if plugin_record is None or not plugin_record_supports_model_discovery(
                    plugin_record,
                ):
                    return None
                if coerce_bool_with_recovery(
                    plugin_record,
                    "persistent",
                    logger=logger,
                    operation=OPERATION_MODEL_DISCOVERY_PLUGIN_PERSISTENCE,
                    default=False,
                ):
                    return await _get_discovery_plugin_instance(
                        plugin_manager,
                        plugin_name,
                        logger,
                    )
                return PluginCheckUnchanged(plugin_name=plugin_name)
        if plugin_state in SKIP_STATES:
            if plugin_state not in PROVIDER_BACKED_IGNORED_PLUGIN_STATES:
                return None
            plugin_success = await _get_discovery_plugin_instance(
                plugin_manager,
                plugin_name,
                logger,
            )
            if not plugin_success:
                return None
            if plugin_success.instance.SUPPORTS_EXTERNAL_PROVIDERS:
                return replace(
                    plugin_success,
                    provider_catalog_only=plugin_state == PLUGIN_STATE_BACKEND_NOT_INSTALLED,
                )
            return None
        return await _get_discovery_plugin_instance(
            plugin_manager,
            plugin_name,
            logger,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_CHECK_PLUGIN,
        )
        return PluginCheckFailure(plugin_name=plugin_name, error=coerced)


async def _call_plugin_provider(
    plugin_check: PluginCheckSuccess,
    coordination: DiscoveryPassCoordination,
) -> dict[str, JSONDict] | None:
    await coordination.provider_phase_open.wait()
    async with coordination.provider_permits:
        started_ms = monotonic_ms()
        response = await plugin_check.instance.discover_models(
            existing_models=coordination.existing_models.get(plugin_check.plugin_name, {}),
        )
        get_logger(LOGGER_NAME).debug(
            "Model discovery provider '%s' completed in %sms.",
            plugin_check.plugin_name,
            monotonic_ms() - started_ms,
        )
        return response


def _settle_provider_result(
    provider_task: asyncio.Task[dict[str, JSONDict] | None],
    plugin_name: str,
    operation: PluginDiscoveryOperationProtocol,
    *,
    provider_catalog_only: bool = False,
) -> PluginDiscoveryResult:
    if operation.superseded:
        if not provider_task.cancelled() and provider_task.exception() is not None:
            operation.record_cleanup_failure()
        return PluginCheckUnchanged(plugin_name=plugin_name)
    if provider_task.cancelled():
        raise asyncio.CancelledError()
    provider_exception = provider_task.exception()
    if isinstance(provider_exception, HANDLED_RUNTIME_EXCEPTIONS):
        coerced = coerce_to_soai_error(
            provider_exception,
            operation=OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_DISCOVER_PLUGIN,
        )
        return coerced
    response = provider_task.result()
    if not isinstance(response, dict):
        return response
    normalized_models: dict[str, JSONDict] = {}
    for model_id, model_info in response.items():
        if not isinstance(model_id, str) or not isinstance(model_info, dict):
            continue
        if not provider_catalog_only or is_provider_backed_model(model_info):
            normalized_models[model_id] = filter_json_mapping(model_info)
    if provider_catalog_only:
        return ProviderCatalogDiscovery(models=normalized_models)
    return normalized_models


async def discover_plugin_models(
    plugin_check: PluginCheckSuccess,
    operation: PluginDiscoveryOperationProtocol,
    coordination: DiscoveryPassCoordination,
    plugin_manager: PluginManagerProtocol,
) -> PluginDiscoveryResult:
    provider_task = create_ephemeral_task(
        _call_plugin_provider(plugin_check, coordination),
        name=f"model-discovery-provider-{plugin_check.plugin_name}",
    )
    if not operation.begin_provider_phase(provider_task.cancel):
        provider_task.cancel()
    try:
        _ = await wait_for_first_completed_tasks({provider_task}, cancel_pending=False)
    finally:
        if not provider_task.done():
            provider_task.cancel()
            await wait_for_task_completion(provider_task, retain_resources_until_complete=True)
        if plugin_check.loaded_for_discovery:
            await uncancel_then_cleanup(
                _release_discovery_plugin_instance(
                    plugin_manager,
                    plugin_check.plugin_name,
                    get_logger(LOGGER_NAME),
                ),
            )
    return _settle_provider_result(
        provider_task,
        plugin_check.plugin_name,
        operation,
        provider_catalog_only=plugin_check.provider_catalog_only,
    )
