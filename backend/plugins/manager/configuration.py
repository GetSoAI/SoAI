"""SoAI - Plugin configuration management [backend/plugins/manager/configuration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.logging.trace import get_logger
from core.models.parameter_schema_document import declared_parameter_names
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict
from core.validation.booleans import parse_bool
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from ruamel.yaml.comments import CommentedMap

    from core.config.value_types import ConfigValue
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "get_plugin_configuration",
    "reconcile_plugin_configuration",
    "refresh_plugin_runtime_configuration",
    "set_plugin_configuration",
)

LOGGER_NAME = "SoAI.plugins.manager.configuration"
OPERATION_PLUGIN_MANAGER_RECONCILE_CONFIG_LOAD = "plugin_manager.reconcile_configuration.load"
OPERATION_PLUGIN_MANAGER_RECONCILE_CONFIG_CREATE = "plugin_manager.reconcile_configuration.create"
OPERATION_PLUGIN_MANAGER_RECONCILE_CONFIG = "plugin_manager.reconcile_configuration.update"


def _reconcile_configuration_values(
    *,
    plugin_name: str,
    loaded_config: ConfigValue,
    default_configuration: JSONDict,
    declared_names: frozenset[str],
) -> JSONDict:
    normalized = normalize_for_json(loaded_config)
    coerced = coerce_json_dict(normalized)
    if coerced is None:
        raise ValidationError(
            f"Configuration for '{plugin_name}' is not a JSON object.",
        )
    reconciled = {
        key: coerced[key] if key in coerced else default_value
        for key, default_value in default_configuration.items()
    }
    reconciled.update(
        {
            key: value
            for key, value in coerced.items()
            if key not in reconciled and key in declared_names
        }
    )
    return reconciled


async def _require_supports_configuration(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    instance = await self.get_plugin_instance(plugin_name)
    if instance is not None:
        self.require_plugin_capability(
            instance,
            "SUPPORTS_CONFIGURATION",
            f"Plugin '{plugin_name}' does not have a managed configuration.",
        )
        return
    plugin_record = await self.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    has_configuration_value = (
        plugin_record.get("has_configuration") if plugin_record is not None else None
    )
    if not parse_bool(has_configuration_value, default=False):
        raise ValidationError(f"Plugin '{plugin_name}' does not have a managed configuration.")


async def get_plugin_configuration(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> JSONDict:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    await _require_supports_configuration(self, plugin_name)
    loaded_config = await self.dependencies.infrastructure.config_manager.load_config(plugin_name)
    if loaded_config is None:
        return {}
    normalized = normalize_for_json(loaded_config)
    coerced = coerce_json_dict(normalized)
    if coerced is None:
        raise ValidationError(f"Configuration for '{plugin_name}' is not a JSON object.")
    return coerced


async def set_plugin_configuration(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    config_data: JSONDict,
    *,
    apply_runtime: bool = True,
) -> bool:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    await _require_supports_configuration(self, plugin_name)
    saved = await self.dependencies.infrastructure.config_manager.save_config(
        plugin_name,
        config_data,
        source="plugin_manager:save_configuration",
    )
    if saved and apply_runtime:
        await refresh_plugin_runtime_configuration(self, plugin_name, auto_load=False)
    return saved


async def refresh_plugin_runtime_configuration(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    auto_load: bool = True,
) -> JSONDict:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    if auto_load:
        instance = await self.require_loaded_plugin(plugin_name, auto_load=True)
    else:
        async with serialized_plugin_load_scope(self, plugin_name):
            instance_optional = await self.get_plugin_instance(plugin_name)
        if instance_optional is None:
            return {}
        instance = instance_optional
    if not supports_plugin_capability_from_instance(instance, "SUPPORTS_CONFIGURATION"):
        return {}
    return await instance.refresh_runtime_configuration()


async def reconcile_plugin_configuration(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    default_configuration: JSONDict,
    *,
    parameter_schema: JSONDict,
) -> tuple[JSONDict | None, bool]:
    logger = get_logger(LOGGER_NAME)
    async with self.dependencies.infrastructure.config_manager.creation_lock_for(plugin_name):
        normalized_default = normalize_for_json(default_configuration)
        coerced_default = coerce_json_dict(normalized_default)
        if coerced_default is None:
            raise ValidationError(
                f"Default configuration for '{plugin_name}' is not a JSON object.",
            )
        try:
            loaded_config = await self.dependencies.infrastructure.config_manager.load_config(
                plugin_name,
                force_reload=True,
            )
        except ConfigurationError as exception:
            trace_id = f"sys_config_load_{plugin_name}_{uuid.uuid4().hex[:12]}"
            log_exception(
                logger,
                exception,
                message=f"Failed to load config for '{plugin_name}'. Plugin cannot be loaded.",
                trace_id=trace_id,
                operation=OPERATION_PLUGIN_MANAGER_RECONCILE_CONFIG_LOAD,
                details={"plugin_name": plugin_name},
                level="critical",
            )
            return (None, False)
        declared_names = frozenset(declared_parameter_names(parameter_schema))
        current_config: ConfigValue = loaded_config if loaded_config is not None else {}
        reconciled = _reconcile_configuration_values(
            plugin_name=plugin_name,
            loaded_config=current_config,
            default_configuration=coerced_default,
            declared_names=declared_names,
        )
        if loaded_config is not None and reconciled == normalize_for_json(loaded_config):
            return (reconciled, True)
        if loaded_config is None:
            logger.info(
                "Configuration for '%s' not found. Creating default from plugin.",
                plugin_name,
            )
        final_reconciled = reconciled

        def apply_latest_config(current: CommentedMap) -> dict[str, JSONValue]:
            nonlocal final_reconciled
            final_reconciled = _reconcile_configuration_values(
                plugin_name=plugin_name,
                loaded_config=current,
                default_configuration=coerced_default,
                declared_names=declared_names,
            )
            return final_reconciled

        try:
            config_manager = self.dependencies.infrastructure.config_manager
            saved = await config_manager.update_config_transactionally(
                plugin_name,
                source=(
                    "plugin_manager:create_default_config"
                    if loaded_config is None
                    else "plugin_manager:reconcile_configuration"
                ),
                updater=apply_latest_config,
            )
            if not saved:
                return (None, False)
            if loaded_config is None:
                logger.info("Successfully created default config for '%s'.", plugin_name)
            return (final_reconciled, True)
        except ConfigurationError as exception:
            creating = loaded_config is None
            trace_prefix = "write" if creating else "reconcile"
            action = "write default" if creating else "reconcile config"
            trace_id = f"sys_config_{trace_prefix}_{plugin_name}_{uuid.uuid4().hex[:12]}"
            if creating:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to {action} for '{plugin_name}'. Plugin cannot be loaded.",
                    trace_id=trace_id,
                    operation=OPERATION_PLUGIN_MANAGER_RECONCILE_CONFIG_CREATE,
                    details={"plugin_name": plugin_name},
                    level="critical",
                )
                return (None, False)
            log_exception(
                logger,
                exception,
                message=f"Failed to {action} for '{plugin_name}'. Plugin cannot be loaded.",
                trace_id=trace_id,
                operation=OPERATION_PLUGIN_MANAGER_RECONCILE_CONFIG,
                details={"plugin_name": plugin_name},
                level="critical",
            )
            return (None, False)
