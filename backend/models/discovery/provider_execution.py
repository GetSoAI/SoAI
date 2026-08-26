"""SoAI - Discovery provider execution and failure handling [backend/models/discovery/provider_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.plugins.catalog_capabilities import plugin_record_supports_model_discovery
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.protocols import StateAggregatorProtocol
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
)
from core.state.state_transition_sets import PLUGIN_DISCOVERY_SKIP_STATES
from core.types.json_value import filter_json_mapping
from core.validation.boolean_coercion import coerce_bool_with_recovery
from models.discovery.provider_bounded_execution import (
    PluginCheckFailure,
    PluginCheckSuccess,
    PluginCheckUnchanged,
    run_bounded_discovery_calls,
    run_bounded_plugin_checks,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PluginCheckFailure",
    "PluginCheckSuccess",
    "PluginCheckUnchanged",
    "run_discovery_providers",
)

LOGGER_NAME = "SoAI.models.discovery.provider_execution"
OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_CHECK_PLUGIN = (
    "model_discovery.run_discovery_providers.check_plugin"
)
OPERATION_MODEL_DISCOVERY_RELEASE_DISCOVERY_PLUGIN = "model_discovery.release_discovery_plugin"
OPERATION_MODEL_DISCOVERY_PLUGIN_PERSISTENCE = "model_discovery.plugin_persistence"


SKIP_STATES = PLUGIN_DISCOVERY_SKIP_STATES


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


async def _release_discovery_plugin_instances(
    plugin_manager: PluginManagerProtocol,
    plugin_names: set[str],
    logger: TraceLogger,
) -> None:
    for plugin_name in sorted(plugin_names):
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


PRE_CHECK_CONCURRENCY_LIMIT = 5
DISCOVERY_CONCURRENCY_LIMIT = 5


async def run_discovery_providers(
    plugins_to_scan: set[str],
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    existing_models: dict[str, dict[str, JSONDict]],
    download_discovery_logged: set[str],
    disabled_discovery_logged: set[str],
    *,
    reuse_existing_models_for_unloaded_plugins: bool = False,
) -> dict[str, dict[str, JSONDict] | Exception | PluginCheckUnchanged | None]:
    logger = get_logger(LOGGER_NAME)

    async def check_plugin(
        plugin_name: str,
    ) -> PluginCheckSuccess | PluginCheckFailure | PluginCheckUnchanged | None:
        try:
            if await plugin_manager.is_model_download_in_progress(plugin_name):
                await plugin_manager.mark_discovery_pending_after_download(plugin_name)
                if plugin_name not in download_discovery_logged:
                    logger.debug(
                        "Skipping discovery for '%s' during active model download.",
                        plugin_name,
                    )
                    download_discovery_logged.add(plugin_name)
                return None
            download_discovery_logged.discard(plugin_name)
            plugin_state = await state_aggregator.get_plugin_status(plugin_name)
            if plugin_state == ORCH_STATE_DISABLED:
                if plugin_name not in disabled_discovery_logged:
                    logger.debug("Skipping discovery for disabled plugin '%s'.", plugin_name)
                    disabled_discovery_logged.add(plugin_name)
                return None
            disabled_discovery_logged.discard(plugin_name)
            if reuse_existing_models_for_unloaded_plugins:
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
                        plugin_success = await _get_discovery_plugin_instance(
                            plugin_manager,
                            plugin_name,
                            logger,
                        )
                        if not plugin_success:
                            return None
                        return plugin_success
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
                    return plugin_success
                return None
            plugin_success = await _get_discovery_plugin_instance(
                plugin_manager,
                plugin_name,
                logger,
            )
            if not plugin_success:
                return None
            return plugin_success
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_CHECK_PLUGIN,
            )
            log_exception(
                logger,
                coerced,
                message=f"Pre-check for plugin '{plugin_name}' failed.",
                operation=OPERATION_MODEL_DISCOVERY_RUN_DISCOVERY_PROVIDERS_CHECK_PLUGIN,
                details={"plugin_name": plugin_name},
            )
            return PluginCheckFailure(plugin_name=plugin_name, error=coerced)

    check_results = await run_bounded_plugin_checks(
        sorted(plugins_to_scan),
        check_plugin,
        PRE_CHECK_CONCURRENCY_LIMIT,
    )
    plugin_instances: dict[str, PluginInstanceProtocol] = {}
    pre_check_failures: dict[str, Exception] = {}
    unchanged_plugin_names: set[str] = set()
    loaded_for_discovery_names: set[str] = set()
    for check_result in check_results:
        if isinstance(check_result, PluginCheckSuccess):
            plugin_instances[check_result.plugin_name] = check_result.instance
            if check_result.loaded_for_discovery:
                loaded_for_discovery_names.add(check_result.plugin_name)
        elif isinstance(check_result, PluginCheckFailure):
            pre_check_failures[check_result.plugin_name] = check_result.error
        elif isinstance(check_result, PluginCheckUnchanged):
            unchanged_plugin_names.add(check_result.plugin_name)

    normalized_results: dict[
        str,
        dict[str, JSONDict] | Exception | PluginCheckUnchanged | None,
    ] = {
        plugin_name: PluginCheckUnchanged(plugin_name=plugin_name)
        for plugin_name in unchanged_plugin_names
    }
    for plugin_name, error in pre_check_failures.items():
        normalized_results[plugin_name] = error

    if not plugin_instances:
        return normalized_results

    async def discover_models(
        plugin_name: str,
        instance: PluginInstanceProtocol,
    ) -> dict[str, JSONDict] | None:
        return await instance.discover_models(existing_models=existing_models.get(plugin_name, {}))

    try:
        discovery_responses = await run_bounded_discovery_calls(
            plugin_instances,
            discover_models,
            DISCOVERY_CONCURRENCY_LIMIT,
        )
    finally:
        await uncancel_then_cleanup(
            _release_discovery_plugin_instances(
                plugin_manager,
                loaded_for_discovery_names,
                logger,
            ),
        )
    raw_results = dict(zip(plugin_instances.keys(), discovery_responses, strict=True))
    for plugin_name, result in raw_results.items():
        if isinstance(result, dict):
            normalized_models: dict[str, JSONDict] = {}
            for model_id, model_info in result.items():
                if not isinstance(model_id, str) or not isinstance(model_info, dict):
                    continue
                normalized_models[model_id] = filter_json_mapping(model_info)
            normalized_results[plugin_name] = normalized_models
        else:
            normalized_results[plugin_name] = result
    return normalized_results
