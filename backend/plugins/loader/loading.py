"""SoAI - Plugin loading and announcement coordinator [backend/plugins/loader/loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    NotFoundError,
    ProcessError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.state.compatibility import CompatibilityInfo
from core.state.state_names import PluginRuntimeStateName
from core.types.json import JSONDict, is_json_dict
from plugins.loader.announcement import announce_loaded_plugin
from plugins.loader.configured_worker_load import load_plugin_worker_with_config
from plugins.loader.incompatibility import handle_incompatible_plugin
from plugins.loader.load_failure import handle_plugin_load_failure
from plugins.loader.loading_existing import build_existing_plugin_load_outcome
from plugins.loader.loading_policy import PluginLoadOutcome, PluginLoadPolicy
from plugins.loader.loading_previous_state import resolve_previous_plugin_state
from plugins.loader.loading_registration import (
    PluginLoadRegistration,
    register_loaded_plugin,
)
from plugins.loader.loading_side_effects import prepare_loaded_plugin_side_effects
from plugins.loader.preflight import (
    PluginPreflightResult,
    perform_plugin_preflight_checks,
)
from plugins.loader.record_data import build_plugin_record_data
from plugins.manager.initial_state import compute_initial_state
from plugins.manager.instances import clear_loaded_plugin_state
from plugins.manifest.runtime_payload import build_runtime_plugin_manifest_payload

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("PLUGIN_LOAD_FAILURE_EXCEPTIONS", "load_and_announce_plugin")

LOGGER_NAME = "SoAI.plugins.loader.loading"
OPERATION_PLUGIN_LOADER_LOAD_PLUGIN_REGISTER_SCHEMA = "plugin_loader.load_plugin.register_schema"
OPERATION_PLUGIN_MANIFEST_EXTRACTION = "plugins.loader.loading.extract_plugin_manifest"
PLUGIN_LOAD_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    NotFoundError,
    ProcessError,
    SecurityError,
    StateError,
    ValidationError,
)


async def load_and_announce_plugin(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    force_reload: bool = False,
    *,
    preflight_result: PluginPreflightResult | None = None,
    policy: PluginLoadPolicy | None = None,
) -> PluginLoadOutcome:
    resolved_policy = policy or PluginLoadPolicy(
        catalog_state=None,
        announce=True,
        publish_failure_state=True,
    )
    logger = get_logger(LOGGER_NAME)
    if plugin_name in manager.state.catalog.loaded_plugin_instances and (not force_reload):
        return await build_existing_plugin_load_outcome(manager, plugin_name)
    parameter_schema_registered = False
    compatibility: CompatibilityInfo | None = None
    existing_record: JSONDict | None = None
    manifest: JSONDict | None = None
    package_audit = None
    previous_state: PluginRuntimeStateName
    try:
        if preflight_result is not None:
            compatibility = preflight_result.compatibility
            existing_record = preflight_result.existing_record
            manifest = preflight_result.manifest
            package_audit = preflight_result.package_audit
        else:
            preflight_result = await perform_plugin_preflight_checks(manager, plugin_name)
            compatibility = preflight_result.compatibility
            existing_record = preflight_result.existing_record
            manifest = preflight_result.manifest
            package_audit = preflight_result.package_audit
        previous_state = await resolve_previous_plugin_state(
            manager,
            plugin_name,
            existing_record=existing_record,
            logger=logger,
        )
        if package_audit is None:
            raise StateError(f"Preflight package audit missing for '{plugin_name}'.")
        if manifest is None:
            raise StateError(f"Preflight manifest missing for '{plugin_name}'.")
        plugin_data = await build_plugin_record_data(
            manager,
            plugin_name,
            plugin_data_override=manifest,
            package_audit=package_audit,
        )
        plugin_data["runtime_loaded"] = True
        loaded_config = await manager.dependencies.infrastructure.config_manager.load_config(
            plugin_name,
        )
        initial_config = dict(loaded_config) if is_json_dict(loaded_config) else {}
        configured_load = await load_plugin_worker_with_config(
            manager=manager,
            plugin_name=plugin_name,
            package_audit=package_audit,
            preflight_result=preflight_result,
            initial_config=initial_config,
        )
        final_instance: PluginInstanceProtocol = configured_load.instance
        default_configuration = configured_load.default_configuration
        parameter_schema = configured_load.parameter_schema
        plugin_data.update(
            await build_runtime_plugin_manifest_payload(
                final_instance,
                default_configuration=default_configuration,
                parameter_schema=parameter_schema,
            ),
        )
        await manager.dependencies.databases.plugins.add_or_update_plugin(
            plugin_data,
            state=resolved_policy.catalog_state,
            incompatibility=(
                compatibility if compatibility is not None and compatibility.reason else None
            ),
            override=compatibility.is_overridden if compatibility is not None else False,
        )
        initial_state, reason = await compute_initial_state(
            manager,
            plugin_name,
            final_instance,
            existing_record,
        )
        final_instance, initial_state, reason = await register_loaded_plugin(
            manager,
            PluginLoadRegistration(
                plugin_name=plugin_name,
                force_reload=force_reload,
                plugin_class_name=str(plugin_data.get("class_name") or "Plugin"),
                compatibility=compatibility,
                existing_record=existing_record,
                plugin_data=plugin_data,
                file_hash=package_audit.content.archive_hash,
                final_instance=final_instance,
                initial_state=initial_state,
                reason=reason,
                persisted_state=resolved_policy.catalog_state,
            ),
        )
        if final_instance is not configured_load.instance:
            parameter_schema = await final_instance.get_parameter_schema()
        try:
            schema = parameter_schema
            await manager.dependencies.models.parameter_manager.register_plugin_parameters(
                plugin_name,
                schema,
            )
            await manager.dependencies.databases.plugins.update_plugin_catalog_metadata(
                plugin_name,
                parameter_schema=schema,
            )
            parameter_schema_registered = True
        except PluginIncompatibleError:
            raise
        except PLUGIN_LOAD_FAILURE_EXCEPTIONS as exception:
            try:
                await manager.dependencies.models.parameter_manager.unregister_plugin_parameters(
                    plugin_name,
                )
            except RECOVERABLE_EXCEPTIONS as unregister_exception:
                log_exception(
                    logger,
                    unregister_exception,
                    message=(
                        f"Failed to unregister partial parameter schema for plugin '{plugin_name}'"
                    ),
                    operation=OPERATION_PLUGIN_LOADER_LOAD_PLUGIN_REGISTER_SCHEMA,
                    details={"plugin": plugin_name},
                    level="warning",
                )
            log_exception(
                logger,
                exception,
                message=f"Failed to register parameter schema for plugin '{plugin_name}'",
                operation=OPERATION_PLUGIN_LOADER_LOAD_PLUGIN_REGISTER_SCHEMA,
                details={"plugin": plugin_name},
            )
            raise
        if manager.dependencies.core.log_manager is not None:
            await asyncio.to_thread(
                manager.dependencies.core.log_manager.attach_streaming_handler_to_plugin,
                plugin_name,
                manager.dependencies.core.config,
            )
        welcome_message = (
            final_instance.WELCOME_MESSAGE
            if isinstance(final_instance.WELCOME_MESSAGE, str)
            else None
        )
        await prepare_loaded_plugin_side_effects(
            manager,
            plugin_name=plugin_name,
            plugin_data=plugin_data,
            final_instance=final_instance,
        )
        if resolved_policy.announce:
            await announce_loaded_plugin(
                manager,
                plugin_name=plugin_name,
                welcome_message=welcome_message,
                plugin_data=plugin_data,
                previous_state=previous_state,
                initial_state=initial_state,
                reason=reason,
            )
        return PluginLoadOutcome(
            instance=final_instance,
            plugin_data=plugin_data,
            previous_state=previous_state,
            initial_state=initial_state,
            reason=reason,
            welcome_message=welcome_message,
        )
    except PluginIncompatibleError as exception:
        await clear_loaded_plugin_state(manager, plugin_name)
        if not resolved_policy.publish_failure_state:
            raise
        plugin_data_override: JSONDict | None = None
        if exception.plugin_class is None:
            plugin_data_override = await build_plugin_record_data(
                manager,
                plugin_name,
                operation=OPERATION_PLUGIN_MANIFEST_EXTRACTION,
                error_message="Plugin loading: manifest could not be read (non-critical).",
            )
        await handle_incompatible_plugin(
            manager,
            exception,
            plugin_data_override=plugin_data_override,
        )
        raise
    except PLUGIN_LOAD_FAILURE_EXCEPTIONS as exception:
        await handle_plugin_load_failure(
            manager=manager,
            plugin_name=plugin_name,
            exception=exception,
            parameter_schema_registered=parameter_schema_registered,
            publish_failure_state=resolved_policy.publish_failure_state,
            logger=logger,
        )
